"""Small habits of the legacy systems: the schedule remembers the week, and the patient
registration sheet prints (legacy Medical fichapaciente_imp). Fictitious data only."""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_paridade", clinica_a, Papel.RECEPCAO))


def test_agenda_volta_na_semana_que_estava_aberta(clinica_a, recepcao, criar_profissional):
    practitioner = criar_profissional(clinica_a, "Profissional fictício")
    semana = {"start": "2026-03-02T00:00:00", "end": "2026-03-09T00:00:00"}
    eventos = recepcao.get(reverse("schedule:events"), {**semana, "practitioner": practitioner.pk})
    assert eventos.status_code == 200
    configuracao = recepcao.get(reverse("schedule:calendar")).context["configuracao"]
    assert configuracao["data"] == "2026-03-05"  # middle of the week on the screen
    # An explicit date still wins.
    explicita = recepcao.get(reverse("schedule:calendar"), {"data": "2026-04-01"})
    assert explicita.context["configuracao"]["data"] == "2026-04-01"


def test_no_dia_seguinte_a_agenda_abre_hoje(recepcao):
    sessao = recepcao.session
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    sessao["agenda_data"] = {"data": "2026-03-05", "em": ontem.isoformat()}
    sessao.save()
    assert recepcao.get(reverse("schedule:calendar")).context["configuracao"]["data"] == ""


def test_ficha_cadastral_impressa(clinica_a, recepcao):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(
            nome="Paciente fictícia da ficha",
            cpf_cnpj="52998224725",
            whatsapp="48999990000",
            observacoes="Prefere manhã",
        )
        convenio = HealthPlan.objects.create(nome="Saúde Exemplo")
        MemberCard.objects.create(patient=patient, convenio=convenio, numero="123456")
    ficha = recepcao.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert reverse("patients:print", args=[patient.pk]) in ficha
    pagina = recepcao.get(reverse("patients:print", args=[patient.pk]))
    texto = pagina.content.decode()
    for trecho in (
        "FICHA CADASTRAL",
        "529.982.247-25",
        "(48) 99999-0000",
        "Saúde Exemplo",
        "Prefere manhã",
    ):
        assert trecho in texto, trecho
    assert (
        AuditEntry.objects.filter(
            acao=AuditEntry.Acao.VISUALIZAR, objeto_id=str(patient.pk)
        ).count()
        == 2
    )  # the record and the print


def test_ficha_impressa_respeita_permissao(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(nome="Paciente fictício sem acesso")
    sem_vinculo = cliente_de(criar_usuario("sem_vinculo_paridade"))
    assert sem_vinculo.get(reverse("patients:print", args=[patient.pk])).status_code in (
        302,
        403,
    )
