"""Medical record (0.29.0, decision 081): anamnesis per visit, for practitioners only."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.medical_records.models import Visit
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

ANAMNESE = {
    "date": "2031-03-05T10:00",
    "queixa_principal": "Dor de cabeça há 3 dias",
    "historia": "Piora à tarde",
    "antecedentes": "Alergia a dipirona",
    "exame_fisico": "PA 12x8",
    "conduta": "Retorno em 7 dias",
}


def cliente(user):
    """A client of its own for each user (the shared fixture logs one user at a time)."""
    novo = Client()
    novo.force_login(user)
    return novo


@pytest.fixture
def cenario(clinica_a, criar_usuario, criar_profissional):
    usuarios = {
        "dra": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
        "dr": criar_usuario("dr", clinica_a, Papel.PROFISSIONAL),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
    }
    ana = criar_profissional(clinica_a, "Dra. Ana")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    with usar_clinica(clinica_a):
        Practitioner.objects.filter(pk=ana.pk).update(user=usuarios["dra"])
        Practitioner.objects.filter(pk=bruno.pk).update(user=usuarios["dr"])
        patient = Patient.objects.create(name="Maria Paciente")
        agendamento = Appointment.objects.create(
            practitioner=ana,
            kind=AppointmentType.objects.first(),
            patient=patient,
            inicio=agenda.momento(datetime.date(2031, 3, 5), datetime.time(10)),
            fim=agenda.momento(datetime.date(2031, 3, 5), datetime.time(11)),
        )
    return {
        "clinic": clinica_a,
        "patient": patient,
        "agendamento": agendamento,
        "ana": ana,
        **{name: cliente(user) for name, user in usuarios.items()},
    }


def registrar(cenario, quem="dra", **extra):
    url = reverse("medical_records:new", args=[cenario["patient"].pk])
    resposta = cenario[quem].post(url, {**ANAMNESE, **extra})
    assert resposta.status_code == 302, resposta.content.decode()[:500]
    with usar_clinica(cenario["clinic"]):
        return Visit.objects.latest("pk")


def test_so_profissionais_veem_o_prontuario(cenario, django_user_model):
    novo = reverse("medical_records:new", args=[cenario["patient"].pk])
    ficha = reverse("patients:record", args=[cenario["patient"].pk])
    for quem in ("recepcao", "admin"):
        assert cenario[quem].get(novo).status_code == 403
        assert "prontuario" not in cenario[quem].get(ficha).context
    # The system administrator always reaches it (decision 087), the clinic administrator not.
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert cliente(root).get(novo).status_code == 200
    pagina = cenario["dra"].get(ficha)
    assert pagina.context["prontuario"] == [] and "Novo atendimento" in pagina.content.decode()

    # An administrator who is also a registered practitioner reaches it.
    with usar_clinica(cenario["clinic"]):
        Practitioner.objects.create(
            name="Dr. Admin", user=django_user_model.objects.get(username="admin")
        )
    assert cenario["admin"].get(novo).status_code == 200


def test_registrar_salvar_e_finalizar(cenario):
    agendamento = cenario["agendamento"]
    visit = registrar(cenario, agendamento=agendamento.pk)
    assert (visit.practitioner, visit.agendamento) == (cenario["ana"], agendamento)
    assert visit.queixa_principal == ANAMNESE["queixa_principal"]
    assert not visit.finalizado
    # The appointment leads to the same visit, never a second one.
    url_novo = reverse("medical_records:new", args=[cenario["patient"].pk])
    resposta = cenario["dra"].get(url_novo, {"agendamento": agendamento.pk})
    assert resposta.url == reverse("medical_records:visit", args=[visit.pk])

    url = reverse("medical_records:visit", args=[visit.pk])
    cenario["dra"].post(url, {**ANAMNESE, "conduta": "Retorno em 15 dias", "acao": "finalizar"})
    visit.refresh_from_db()
    assert visit.finalizado and visit.conduta == "Retorno em 15 dias"

    # Finalized: nobody changes it any more, corrections are addenda.
    assert cenario["dra"].post(url, {**ANAMNESE, "conduta": "outra"}).status_code == 403
    pagina = cenario["dra"].get(url)
    assert pagina.context["form"] is None and pagina.context["adendo_form"] is not None
    cenario["dr"].post(reverse("medical_records:addendum", args=[visit.pk]), {"texto": "Exame ok"})
    with usar_clinica(cenario["clinic"]):
        adendo = visit.adendos.get()
    assert adendo.texto == "Exame ok" and adendo.practitioner.name == "Dr. Bruno"
    assert "Exame ok" in cenario["dra"].get(url).content.decode()


def test_rascunho_so_o_autor_altera(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:visit", args=[visit.pk])
    pagina = cenario["dr"].get(url)
    assert pagina.context["form"] is None and pagina.context["adendo_form"] is None
    assert cenario["dr"].post(url, {**ANAMNESE, "conduta": "outra"}).status_code == 403
    # No addendum before it is finalized: the author edits the draft instead.
    adendo = reverse("medical_records:addendum", args=[visit.pk])
    assert cenario["dra"].post(adendo, {"texto": "x"}).status_code == 403


def test_auditoria_registra_sem_copiar_o_texto_clinico(cenario):
    visit = registrar(cenario)
    cenario["dr"].get(reverse("medical_records:visit", args=[visit.pk]))
    registros = AuditEntry.objects.filter(modelo="Atendimento", objeto_id=visit.pk)
    assert {r.acao for r in registros} == {"criar", "visualizar"}
    conteudo = str([r.alteracoes for r in registros])
    assert "(conteúdo clínico)" in conteudo
    for texto in ANAMNESE.values():
        if not texto.startswith("2031"):
            assert texto not in conteudo


def test_paciente_com_prontuario_nao_e_excluido(cenario, django_user_model):
    registrar(cenario)
    patient = cenario["patient"]
    with usar_clinica(cenario["clinic"]):
        Patient.objects.filter(pk=patient.pk).update(arquivado=True, arquivado_em=timezone.now())
    url = reverse("patients:delete", args=[patient.pk])
    pagina = cenario["admin"].get(url)
    assert pagina.context["atendimentos"] == 1 and "20 anos" in pagina.content.decode()
    cenario["admin"].post(url)
    with usar_clinica(cenario["clinic"]):
        assert Patient.objects.filter(pk=patient.pk).exists()


def test_agenda_leva_ao_atendimento_so_para_profissionais(cenario):
    editar = reverse("schedule:edit", args=[cenario["agendamento"].pk])
    assert "Registrar atendimento" in cenario["dra"].get(editar).content.decode()
    assert "Registrar atendimento" not in cenario["recepcao"].get(editar).content.decode()
    visit = registrar(cenario, agendamento=cenario["agendamento"].pk)
    pagina = cenario["dra"].get(editar).content.decode()
    assert reverse("medical_records:visit", args=[visit.pk]) in pagina


def test_imprimir_so_depois_de_finalizado(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:print", args=[visit.pk])
    assert cenario["dra"].get(url).status_code == 403
    pagina = cenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert url not in pagina.content.decode()
    cenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]),
        {**ANAMNESE, "acao": "finalizar"},
    )
    impressao = cenario["dr"].get(url)
    conteudo = impressao.content.decode()
    assert impressao.status_code == 200
    assert ANAMNESE["queixa_principal"] in conteudo and "Dra. Ana" in conteudo
    assert AuditEntry.objects.filter(
        objeto_id=visit.pk, acao="visualizar", objeto_descricao__endswith="(impressão)"
    ).exists()
    assert cenario["recepcao"].get(url).status_code == 403


def test_atestado_de_comparecimento_e_de_afastamento(cenario):
    visit = registrar(cenario, agendamento=cenario["agendamento"].pk)
    url = reverse("medical_records:certificate_new", args=[visit.pk])
    # The appointment's times come filled in.
    formulario = cenario["dra"].get(url).context["form"]
    assert formulario.initial["hora_inicio"] == datetime.time(10)
    assert formulario.initial["hora_fim"] == datetime.time(11)

    resposta = cenario["dra"].post(
        url,
        {
            "kind": "comparecimento",
            "date": "2031-03-05",
            "hora_inicio": "10:00",
            "hora_fim": "11:00",
        },
    )
    pagina = cenario["dra"].get(resposta.url).content.decode()
    assert "Maria Paciente" in pagina and "das 10:00 às 11:00" in pagina

    sem_dias = cenario["dra"].post(url, {"kind": "afastamento", "date": "2031-03-05"})
    assert "Informe quantos dias" in sem_dias.content.decode()
    resposta = cenario["dra"].post(
        url, {"kind": "afastamento", "date": "2031-03-05", "dias": "3", "note": "Repouso"}
    )
    pagina = cenario["dra"].get(resposta.url).content.decode()
    assert "3 dias de afastamento" in pagina and "Repouso" in pagina
    assert "5 de março de 2031" in pagina  # month in lower case, as in running text
    with usar_clinica(cenario["clinic"]):
        assert visit.atestados.count() == 2
    registro = AuditEntry.objects.filter(modelo="Atestado").latest("pk")
    assert "Repouso" not in str(registro.alteracoes)

    # Only the visit's author issues documents; other practitioners print them.
    assert cenario["dr"].get(url).status_code == 403
    assert cenario["dr"].get(resposta.url).status_code == 200
    assert cenario["recepcao"].get(resposta.url).status_code == 403


def test_receita_uma_linha_por_item(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:prescription_new", args=[visit.pk])
    prescricao = "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas\n\nSoro fisiológico nasal"
    resposta = cenario["dra"].post(url, {"prescricao": prescricao})
    pagina = cenario["dra"].get(resposta.url)
    assert pagina.context["linhas"] == [
        "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas",
        "Soro fisiológico nasal",
    ]
    assert "RECEITUÁRIO" in pagina.content.decode()
    ficha = cenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert resposta.url in ficha.content.decode()
    registro = AuditEntry.objects.filter(modelo="Receita").latest("pk")
    assert "Paracetamol" not in str(registro.alteracoes)


def test_pedido_de_exames(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:exam_request_new", args=[visit.pk])
    resposta = cenario["dra"].post(
        url, {"exames": "Hemograma completo\nGlicemia de jejum", "indicacao": "Rotina"}
    )
    pagina = cenario["dr"].get(resposta.url)
    assert pagina.context["linhas"] == ["Hemograma completo", "Glicemia de jejum"]
    assert "PEDIDO DE EXAMES" in pagina.content.decode() and "Rotina" in pagina.content.decode()
    assert cenario["dr"].get(url).status_code == 403  # only the visit's author issues
    registro = AuditEntry.objects.filter(modelo="Pedido de exames").latest("pk")
    assert "Hemograma" not in str(registro.alteracoes)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_anexos_so_pdf_jpg_png_e_so_para_profissionais(cenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = registrar(cenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    enviar = lambda quem, name, conteudo: cenario[quem].post(  # noqa: E731
        url, {"arquivo": SimpleUploadedFile(name, conteudo), "description": "Raio-X"}, follow=True
    )
    # Checked by the content, not the name: an HTML page named .png is refused.
    assert (
        "Envie um arquivo PDF, JPG ou PNG" in enviar("dra", "foto.png", b"<html>").content.decode()
    )
    grande = b"%PDF-" + b"0" * (10 * 1024 * 1024)
    assert "passa de 10 MB" in enviar("dra", "laudo.pdf", grande).content.decode()
    assert (
        cenario["recepcao"].post(url, {"arquivo": SimpleUploadedFile("x.png", PNG)}).status_code
        == 403
    )

    enviar("dr", "raio-x paciente.png", PNG)  # another practitioner, results arrive later
    with usar_clinica(cenario["clinic"]):
        anexo = Attachment.objects.get()
    assert (anexo.kind, anexo.tamanho, anexo.practitioner.name) == (
        "image/png",
        len(PNG),
        "Dr. Bruno",
    )

    arquivo = cenario["dra"].get(reverse("medical_records:attachment", args=[anexo.pk]))
    assert arquivo.content == PNG and arquivo["Content-Type"] == "image/png"
    assert arquivo["Cache-Control"] == "private, no-store"
    assert (
        cenario["recepcao"].get(reverse("medical_records:attachment", args=[anexo.pk])).status_code
        == 403
    )
    assert "raio-x" not in str(
        list(
            AuditEntry.objects.filter(modelo="Anexo").values_list("objeto_descricao", "alteracoes")
        )
    )


def test_anexo_removido_so_por_quem_enviou_e_antes_de_finalizar(cenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = registrar(cenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    cenario["dra"].post(url, {"arquivo": SimpleUploadedFile("a.png", PNG)})
    cenario["dra"].post(url, {"arquivo": SimpleUploadedFile("b.png", PNG)})
    with usar_clinica(cenario["clinic"]):
        primeiro, segundo = Attachment.objects.order_by("pk")
    remover = lambda anexo: reverse("medical_records:attachment_remove", args=[anexo.pk])  # noqa: E731
    assert cenario["dr"].post(remover(primeiro)).status_code == 403
    cenario["dra"].post(remover(primeiro))
    cenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]), {**ANAMNESE, "acao": "finalizar"}
    )
    assert cenario["dra"].post(remover(segundo)).status_code == 403
    with usar_clinica(cenario["clinic"]):
        assert list(Attachment.objects.values_list("pk", flat=True)) == [segundo.pk]


def test_administrador_do_sistema_ve_e_faz_tudo(cenario, django_user_model):
    """The superuser writes on behalf of a chosen practitioner and edits anyone's draft."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment, Certificate

    root = cliente(django_user_model.objects.create_superuser("root", password="x-12345678"))
    novo = reverse("medical_records:new", args=[cenario["patient"].pk])
    assert 'name="practitioner"' in root.get(novo).content.decode()
    resposta = root.post(novo, {**ANAMNESE, "practitioner": cenario["ana"].pk})
    assert resposta.status_code == 302
    with usar_clinica(cenario["clinic"]):
        visit = Visit.objects.get()
    assert visit.practitioner == cenario["ana"]
    assert visit.created_by.username == "root"  # the audit keeps who really wrote it

    # Another practitioner's draft (Dra. Ana's) can be edited by the superuser only.
    url = reverse("medical_records:visit", args=[visit.pk])
    assert cenario["dr"].post(url, {**ANAMNESE, "conduta": "x"}).status_code == 403
    assert root.post(url, {**ANAMNESE, "conduta": "Retorno em 15 dias"}).status_code == 302
    anexo_url = reverse("medical_records:attachment_upload", args=[visit.pk])
    cenario["dra"].post(
        anexo_url, {"arquivo": SimpleUploadedFile("x.png", PNG), "description": "Foto"}
    )
    with usar_clinica(cenario["clinic"]):
        anexo = Attachment.objects.get()
    assert (
        root.post(reverse("medical_records:attachment_remove", args=[anexo.pk])).status_code == 302
    )

    root.post(url, {**ANAMNESE, "acao": "finalizar"})
    resposta = root.post(
        reverse("medical_records:certificate_new", args=[visit.pk]),
        {
            "kind": "comparecimento",
            "date": "2031-03-05",
            "hora_inicio": "10:00",
            "hora_fim": "11:00",
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(cenario["clinic"]):
        assert Certificate.objects.get().practitioner == cenario["ana"]
        assert not Attachment.objects.exists()
    root.post(reverse("medical_records:addendum", args=[visit.pk]), {"texto": "Correção"})
    with usar_clinica(cenario["clinic"]):
        assert visit.adendos.get().practitioner == cenario["ana"]
