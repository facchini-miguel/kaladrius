"""Medical record (0.29.0, decision 081): anamnesis per visit, for practitioners only."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.agenda import servicos as agenda
from apps.agenda.models import Agendamento, TipoAtendimento
from apps.auditoria.models import RegistroAuditoria
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.prontuario.models import Atendimento

pytestmark = pytest.mark.django_db

ANAMNESE = {
    "data": "2031-03-05T10:00",
    "queixa_principal": "Dor de cabeça há 3 dias",
    "historia": "Piora à tarde",
    "antecedentes": "Alergia a dipirona",
    "exame_fisico": "PA 12x8",
    "conduta": "Retorno em 7 dias",
}


def cliente(usuario):
    """A client of its own for each user (the shared fixture logs one user at a time)."""
    novo = Client()
    novo.force_login(usuario)
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
        Profissional.objects.filter(pk=ana.pk).update(usuario=usuarios["dra"])
        Profissional.objects.filter(pk=bruno.pk).update(usuario=usuarios["dr"])
        paciente = Paciente.objects.create(nome="Maria Paciente")
        agendamento = Agendamento.objects.create(
            profissional=ana,
            tipo=TipoAtendimento.objects.first(),
            paciente=paciente,
            inicio=agenda.momento(datetime.date(2031, 3, 5), datetime.time(10)),
            fim=agenda.momento(datetime.date(2031, 3, 5), datetime.time(11)),
        )
    return {
        "clinica": clinica_a,
        "paciente": paciente,
        "agendamento": agendamento,
        "ana": ana,
        **{nome: cliente(usuario) for nome, usuario in usuarios.items()},
    }


def registrar(cenario, quem="dra", **extra):
    url = reverse("prontuario:novo", args=[cenario["paciente"].pk])
    resposta = cenario[quem].post(url, {**ANAMNESE, **extra})
    assert resposta.status_code == 302, resposta.content.decode()[:500]
    with usar_clinica(cenario["clinica"]):
        return Atendimento.objects.latest("pk")


def test_so_profissionais_veem_o_prontuario(cenario, django_user_model):
    novo = reverse("prontuario:novo", args=[cenario["paciente"].pk])
    ficha = reverse("pacientes:ficha", args=[cenario["paciente"].pk])
    for quem in ("recepcao", "admin"):
        assert cenario[quem].get(novo).status_code == 403
        assert "prontuario" not in cenario[quem].get(ficha).context
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert cliente(root).get(novo).status_code == 403  # support account, not a practitioner
    pagina = cenario["dra"].get(ficha)
    assert pagina.context["prontuario"] == [] and "Novo atendimento" in pagina.content.decode()

    # An administrator who is also a registered practitioner reaches it.
    with usar_clinica(cenario["clinica"]):
        Profissional.objects.create(
            nome="Dr. Admin", usuario=django_user_model.objects.get(username="admin")
        )
    assert cenario["admin"].get(novo).status_code == 200


def test_registrar_salvar_e_finalizar(cenario):
    agendamento = cenario["agendamento"]
    atendimento = registrar(cenario, agendamento=agendamento.pk)
    assert (atendimento.profissional, atendimento.agendamento) == (cenario["ana"], agendamento)
    assert atendimento.queixa_principal == ANAMNESE["queixa_principal"]
    assert not atendimento.finalizado
    # The appointment leads to the same visit, never a second one.
    url_novo = reverse("prontuario:novo", args=[cenario["paciente"].pk])
    resposta = cenario["dra"].get(url_novo, {"agendamento": agendamento.pk})
    assert resposta.url == reverse("prontuario:atendimento", args=[atendimento.pk])

    url = reverse("prontuario:atendimento", args=[atendimento.pk])
    cenario["dra"].post(url, {**ANAMNESE, "conduta": "Retorno em 15 dias", "acao": "finalizar"})
    atendimento.refresh_from_db()
    assert atendimento.finalizado and atendimento.conduta == "Retorno em 15 dias"

    # Finalized: nobody changes it any more, corrections are addenda.
    assert cenario["dra"].post(url, {**ANAMNESE, "conduta": "outra"}).status_code == 403
    pagina = cenario["dra"].get(url)
    assert pagina.context["form"] is None and pagina.context["adendo_form"] is not None
    cenario["dr"].post(reverse("prontuario:adendo", args=[atendimento.pk]), {"texto": "Exame ok"})
    with usar_clinica(cenario["clinica"]):
        adendo = atendimento.adendos.get()
    assert adendo.texto == "Exame ok" and adendo.profissional.nome == "Dr. Bruno"
    assert "Exame ok" in cenario["dra"].get(url).content.decode()


def test_rascunho_so_o_autor_altera(cenario):
    atendimento = registrar(cenario)
    url = reverse("prontuario:atendimento", args=[atendimento.pk])
    pagina = cenario["dr"].get(url)
    assert pagina.context["form"] is None and pagina.context["adendo_form"] is None
    assert cenario["dr"].post(url, {**ANAMNESE, "conduta": "outra"}).status_code == 403
    # No addendum before it is finalized: the author edits the draft instead.
    adendo = reverse("prontuario:adendo", args=[atendimento.pk])
    assert cenario["dra"].post(adendo, {"texto": "x"}).status_code == 403


def test_auditoria_registra_sem_copiar_o_texto_clinico(cenario):
    atendimento = registrar(cenario)
    cenario["dr"].get(reverse("prontuario:atendimento", args=[atendimento.pk]))
    registros = RegistroAuditoria.objects.filter(modelo="Atendimento", objeto_id=atendimento.pk)
    assert {r.acao for r in registros} == {"criar", "visualizar"}
    conteudo = str([r.alteracoes for r in registros])
    assert "(conteúdo clínico)" in conteudo
    for texto in ANAMNESE.values():
        if not texto.startswith("2031"):
            assert texto not in conteudo


def test_paciente_com_prontuario_nao_e_excluido(cenario, django_user_model):
    registrar(cenario)
    paciente = cenario["paciente"]
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.filter(pk=paciente.pk).update(arquivado=True, arquivado_em=timezone.now())
    url = reverse("pacientes:excluir", args=[paciente.pk])
    pagina = cenario["admin"].get(url)
    assert pagina.context["atendimentos"] == 1 and "20 anos" in pagina.content.decode()
    cenario["admin"].post(url)
    with usar_clinica(cenario["clinica"]):
        assert Paciente.objects.filter(pk=paciente.pk).exists()


def test_agenda_leva_ao_atendimento_so_para_profissionais(cenario):
    editar = reverse("agenda:editar", args=[cenario["agendamento"].pk])
    assert "Registrar atendimento" in cenario["dra"].get(editar).content.decode()
    assert "Registrar atendimento" not in cenario["recepcao"].get(editar).content.decode()
    atendimento = registrar(cenario, agendamento=cenario["agendamento"].pk)
    pagina = cenario["dra"].get(editar).content.decode()
    assert reverse("prontuario:atendimento", args=[atendimento.pk]) in pagina
