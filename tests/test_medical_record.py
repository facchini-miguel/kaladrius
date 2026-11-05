"""Medical record (0.29.0, decision 081): anamnesis per visit, for practitioners only."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.medical_records.models import Visit
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

ANAMNESE = {
    "date": "2031-03-05T10:00",
    "chief_complaint": "Dor de cabeça há 3 dias",
    "present_illness": "Piora à tarde",
    "medical_history": "Alergia a dipirona",
    "physical_exam": "PA 12x8",
    "plan": "Retorno em 7 dias",
}


def cliente(user):
    """A client of its own for each user (the shared fixture logs one user at a time)."""
    new_visit = Client()
    new_visit.force_login(user)
    return new_visit


@pytest.fixture
def cenario(clinica_a, criar_usuario, criar_profissional):
    usuarios = {
        "dra": criar_usuario("dra", clinica_a, Role.PRACTITIONER),
        "dr": criar_usuario("dr", clinica_a, Role.PRACTITIONER),
        "recepcao": criar_usuario("recepcao", clinica_a, Role.FRONT_DESK),
        "admin": criar_usuario("admin", clinica_a, Role.ADMIN),
    }
    ana = criar_profissional(clinica_a, "Dra. Ana")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    with use_clinic(clinica_a):
        Practitioner.objects.filter(pk=ana.pk).update(user=usuarios["dra"])
        Practitioner.objects.filter(pk=bruno.pk).update(user=usuarios["dr"])
        patient = Patient.objects.create(name="Maria Paciente")
        appointment = Appointment.objects.create(
            practitioner=ana,
            kind=AppointmentType.objects.first(),
            patient=patient,
            start=agenda.timestamp(datetime.date(2031, 3, 5), datetime.time(10)),
            end=agenda.timestamp(datetime.date(2031, 3, 5), datetime.time(11)),
        )
    return {
        "clinic": clinica_a,
        "patient": patient,
        "appointment": appointment,
        "ana": ana,
        **{name: cliente(user) for name, user in usuarios.items()},
    }


def registrar(cenario, quem="dra", **extra):
    url = reverse("medical_records:new", args=[cenario["patient"].pk])
    response = cenario[quem].post(url, {**ANAMNESE, **extra})
    assert response.status_code == 302, response.content.decode()[:500]
    with use_clinic(cenario["clinic"]):
        return Visit.objects.latest("pk")


def test_so_profissionais_veem_o_prontuario(cenario, django_user_model):
    new_visit = reverse("medical_records:new", args=[cenario["patient"].pk])
    patient_record = reverse("patients:record", args=[cenario["patient"].pk])
    for quem in ("recepcao", "admin"):
        assert cenario[quem].get(new_visit).status_code == 403
        assert "prontuario" not in cenario[quem].get(patient_record).context
    # The system administrator always reaches it (decision 087), the clinic administrator not.
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert cliente(root).get(new_visit).status_code == 200
    page = cenario["dra"].get(patient_record)
    assert page.context["prontuario"] == [] and "Novo atendimento" in page.content.decode()

    # An administrator who is also a registered practitioner reaches it.
    with use_clinic(cenario["clinic"]):
        Practitioner.objects.create(
            name="Dr. Admin", user=django_user_model.objects.get(username="admin")
        )
    assert cenario["admin"].get(new_visit).status_code == 200


def test_registrar_salvar_e_finalizar(cenario):
    appointment = cenario["appointment"]
    visit = registrar(cenario, appointment=appointment.pk)
    assert (visit.practitioner, visit.appointment) == (cenario["ana"], appointment)
    assert visit.chief_complaint == ANAMNESE["chief_complaint"]
    assert not visit.is_finalized
    # The appointment leads to the same visit, never a second one.
    url_novo = reverse("medical_records:new", args=[cenario["patient"].pk])
    response = cenario["dra"].get(url_novo, {"appointment": appointment.pk})
    assert response.url == reverse("medical_records:visit", args=[visit.pk])

    url = reverse("medical_records:visit", args=[visit.pk])
    cenario["dra"].post(url, {**ANAMNESE, "plan": "Retorno em 15 dias", "acao": "finalizar"})
    visit.refresh_from_db()
    assert visit.is_finalized and visit.plan == "Retorno em 15 dias"

    # Finalized: nobody changes it any more, corrections are addenda.
    assert cenario["dra"].post(url, {**ANAMNESE, "plan": "outra"}).status_code == 403
    page = cenario["dra"].get(url)
    assert page.context["form"] is None and page.context["adendo_form"] is not None
    cenario["dr"].post(reverse("medical_records:addendum", args=[visit.pk]), {"text": "Exame ok"})
    with use_clinic(cenario["clinic"]):
        addendum = visit.adendos.get()
    assert addendum.text == "Exame ok" and addendum.practitioner.name == "Dr. Bruno"
    assert "Exame ok" in cenario["dra"].get(url).content.decode()


def test_rascunho_so_o_autor_altera(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:visit", args=[visit.pk])
    page = cenario["dr"].get(url)
    assert page.context["form"] is None and page.context["adendo_form"] is None
    assert cenario["dr"].post(url, {**ANAMNESE, "plan": "outra"}).status_code == 403
    # No addendum before it is finalized: the author edits the draft instead.
    addendum = reverse("medical_records:addendum", args=[visit.pk])
    assert cenario["dra"].post(addendum, {"text": "x"}).status_code == 403


def test_auditoria_registra_sem_copiar_o_texto_clinico(cenario):
    visit = registrar(cenario)
    cenario["dr"].get(reverse("medical_records:visit", args=[visit.pk]))
    registros = AuditEntry.objects.filter(model_name="Atendimento", object_id=visit.pk)
    assert {r.action for r in registros} == {"criar", "visualizar"}
    content = str([r.changes for r in registros])
    assert "(conteúdo clínico)" in content
    for text in ANAMNESE.values():
        if not text.startswith("2031"):
            assert text not in content


def test_paciente_com_prontuario_nao_e_excluido(cenario, django_user_model):
    registrar(cenario)
    patient = cenario["patient"]
    with use_clinic(cenario["clinic"]):
        Patient.objects.filter(pk=patient.pk).update(archived=True, archived_at=timezone.now())
    url = reverse("patients:delete", args=[patient.pk])
    page = cenario["admin"].get(url)
    assert page.context["atendimentos"] == 1 and "20 anos" in page.content.decode()
    cenario["admin"].post(url)
    with use_clinic(cenario["clinic"]):
        assert Patient.objects.filter(pk=patient.pk).exists()


def test_agenda_leva_ao_atendimento_so_para_profissionais(cenario):
    editar = reverse("schedule:edit", args=[cenario["appointment"].pk])
    assert "Registrar atendimento" in cenario["dra"].get(editar).content.decode()
    assert "Registrar atendimento" not in cenario["recepcao"].get(editar).content.decode()
    visit = registrar(cenario, appointment=cenario["appointment"].pk)
    page = cenario["dra"].get(editar).content.decode()
    assert reverse("medical_records:visit", args=[visit.pk]) in page


def test_imprimir_so_depois_de_finalizado(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:print", args=[visit.pk])
    assert cenario["dra"].get(url).status_code == 403
    page = cenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert url not in page.content.decode()
    cenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]),
        {**ANAMNESE, "acao": "finalizar"},
    )
    impressao = cenario["dr"].get(url)
    content = impressao.content.decode()
    assert impressao.status_code == 200
    assert ANAMNESE["chief_complaint"] in content and "Dra. Ana" in content
    assert AuditEntry.objects.filter(
        object_id=visit.pk, action="visualizar", object_repr__endswith="(impressão)"
    ).exists()
    assert cenario["recepcao"].get(url).status_code == 403


def test_atestado_de_comparecimento_e_de_afastamento(cenario):
    visit = registrar(cenario, appointment=cenario["appointment"].pk)
    url = reverse("medical_records:certificate_new", args=[visit.pk])
    # The appointment's times come filled in.
    formulario = cenario["dra"].get(url).context["form"]
    assert formulario.initial["start_time"] == datetime.time(10)
    assert formulario.initial["end_time"] == datetime.time(11)

    response = cenario["dra"].post(
        url,
        {
            "kind": "comparecimento",
            "date": "2031-03-05",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    page = cenario["dra"].get(response.url).content.decode()
    assert "Maria Paciente" in page and "das 10:00 às 11:00" in page

    sem_dias = cenario["dra"].post(url, {"kind": "afastamento", "date": "2031-03-05"})
    assert "Informe quantos dias" in sem_dias.content.decode()
    response = cenario["dra"].post(
        url, {"kind": "afastamento", "date": "2031-03-05", "days": "3", "note": "Repouso"}
    )
    page = cenario["dra"].get(response.url).content.decode()
    assert "3 dias de afastamento" in page and "Repouso" in page
    assert "5 de março de 2031" in page  # month in lower case, as in running text
    with use_clinic(cenario["clinic"]):
        assert visit.atestados.count() == 2
    record = AuditEntry.objects.filter(model_name="Atestado").latest("pk")
    assert "Repouso" not in str(record.changes)

    # Only the visit's author issues documents; other practitioners print them.
    assert cenario["dr"].get(url).status_code == 403
    assert cenario["dr"].get(response.url).status_code == 200
    assert cenario["recepcao"].get(response.url).status_code == 403


def test_receita_uma_linha_por_item(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:prescription_new", args=[visit.pk])
    medications = "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas\n\nSoro fisiológico nasal"
    response = cenario["dra"].post(url, {"medications": medications})
    page = cenario["dra"].get(response.url)
    assert page.context["linhas"] == [
        "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas",
        "Soro fisiológico nasal",
    ]
    assert "RECEITUÁRIO" in page.content.decode()
    patient_record = cenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert response.url in patient_record.content.decode()
    record = AuditEntry.objects.filter(model_name="Receita").latest("pk")
    assert "Paracetamol" not in str(record.changes)


def test_pedido_de_exames(cenario):
    visit = registrar(cenario)
    url = reverse("medical_records:exam_request_new", args=[visit.pk])
    response = cenario["dra"].post(
        url, {"exams": "Hemograma completo\nGlicemia de jejum", "indication": "Rotina"}
    )
    page = cenario["dr"].get(response.url)
    assert page.context["linhas"] == ["Hemograma completo", "Glicemia de jejum"]
    assert "PEDIDO DE EXAMES" in page.content.decode() and "Rotina" in page.content.decode()
    assert cenario["dr"].get(url).status_code == 403  # only the visit's author issues
    record = AuditEntry.objects.filter(model_name="Pedido de exames").latest("pk")
    assert "Hemograma" not in str(record.changes)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_anexos_so_pdf_jpg_png_e_so_para_profissionais(cenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = registrar(cenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    enviar = lambda quem, name, content: cenario[quem].post(  # noqa: E731
        url, {"file": SimpleUploadedFile(name, content), "description": "Raio-X"}, follow=True
    )
    # Checked by the content, not the name: an HTML page named .png is refused.
    assert (
        "Envie um arquivo PDF, JPG ou PNG" in enviar("dra", "foto.png", b"<html>").content.decode()
    )
    grande = b"%PDF-" + b"0" * (10 * 1024 * 1024)
    assert "passa de 10 MB" in enviar("dra", "laudo.pdf", grande).content.decode()
    assert (
        cenario["recepcao"].post(url, {"file": SimpleUploadedFile("x.png", PNG)}).status_code == 403
    )

    enviar("dr", "raio-x paciente.png", PNG)  # another practitioner, results arrive later
    with use_clinic(cenario["clinic"]):
        attachment = Attachment.objects.get()
    assert (attachment.kind, attachment.size, attachment.practitioner.name) == (
        "image/png",
        len(PNG),
        "Dr. Bruno",
    )

    file = cenario["dra"].get(reverse("medical_records:attachment", args=[attachment.pk]))
    assert file.content == PNG and file["Content-Type"] == "image/png"
    assert file["Cache-Control"] == "private, no-store"
    assert (
        cenario["recepcao"]
        .get(reverse("medical_records:attachment", args=[attachment.pk]))
        .status_code
        == 403
    )
    assert "raio-x" not in str(
        list(AuditEntry.objects.filter(model_name="Anexo").values_list("object_repr", "changes"))
    )


def test_anexo_removido_so_por_quem_enviou_e_antes_de_finalizar(cenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = registrar(cenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    cenario["dra"].post(url, {"file": SimpleUploadedFile("a.png", PNG)})
    cenario["dra"].post(url, {"file": SimpleUploadedFile("b.png", PNG)})
    with use_clinic(cenario["clinic"]):
        first, segundo = Attachment.objects.order_by("pk")
    remover = lambda attachment: reverse("medical_records:attachment_remove", args=[attachment.pk])  # noqa: E731
    assert cenario["dr"].post(remover(first)).status_code == 403
    cenario["dra"].post(remover(first))
    cenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]), {**ANAMNESE, "acao": "finalizar"}
    )
    assert cenario["dra"].post(remover(segundo)).status_code == 403
    with use_clinic(cenario["clinic"]):
        assert list(Attachment.objects.values_list("pk", flat=True)) == [segundo.pk]


def test_administrador_do_sistema_ve_e_faz_tudo(cenario, django_user_model):
    """The superuser writes on behalf of a chosen practitioner and edits anyone's draft."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment, Certificate

    root = cliente(django_user_model.objects.create_superuser("root", password="x-12345678"))
    new_visit = reverse("medical_records:new", args=[cenario["patient"].pk])
    assert 'name="practitioner"' in root.get(new_visit).content.decode()
    response = root.post(new_visit, {**ANAMNESE, "practitioner": cenario["ana"].pk})
    assert response.status_code == 302
    with use_clinic(cenario["clinic"]):
        visit = Visit.objects.get()
    assert visit.practitioner == cenario["ana"]
    assert visit.created_by.username == "root"  # the audit keeps who really wrote it

    # Another practitioner's draft (Dra. Ana's) can be edited by the superuser only.
    url = reverse("medical_records:visit", args=[visit.pk])
    assert cenario["dr"].post(url, {**ANAMNESE, "plan": "x"}).status_code == 403
    assert root.post(url, {**ANAMNESE, "plan": "Retorno em 15 dias"}).status_code == 302
    anexo_url = reverse("medical_records:attachment_upload", args=[visit.pk])
    cenario["dra"].post(
        anexo_url, {"file": SimpleUploadedFile("x.png", PNG), "description": "Foto"}
    )
    with use_clinic(cenario["clinic"]):
        attachment = Attachment.objects.get()
    assert (
        root.post(reverse("medical_records:attachment_remove", args=[attachment.pk])).status_code
        == 302
    )

    root.post(url, {**ANAMNESE, "acao": "finalizar"})
    response = root.post(
        reverse("medical_records:certificate_new", args=[visit.pk]),
        {
            "kind": "comparecimento",
            "date": "2031-03-05",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    assert response.status_code == 302
    with use_clinic(cenario["clinic"]):
        assert Certificate.objects.get().practitioner == cenario["ana"]
        assert not Attachment.objects.exists()
    root.post(reverse("medical_records:addendum", args=[visit.pk]), {"text": "Correção"})
    with use_clinic(cenario["clinic"]):
        assert visit.adendos.get().practitioner == cenario["ana"]
