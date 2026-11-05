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
def reception(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_paridade", clinica_a, Papel.RECEPCAO))


def test_agenda_volta_na_semana_que_estava_aberta(clinica_a, reception, criar_profissional):
    practitioner = criar_profissional(clinica_a, "Profissional fictício")
    week = {"start": "2026-03-02T00:00:00", "end": "2026-03-09T00:00:00"}
    eventos = reception.get(reverse("schedule:events"), {**week, "practitioner": practitioner.pk})
    assert eventos.status_code == 200
    config = reception.get(reverse("schedule:calendar")).context["configuracao"]
    assert config["date"] == "2026-03-05"  # middle of the week on the screen
    # An explicit date still wins.
    explicita = reception.get(reverse("schedule:calendar"), {"date": "2026-04-01"})
    assert explicita.context["configuracao"]["date"] == "2026-04-01"


def test_no_dia_seguinte_a_agenda_abre_hoje(reception):
    session = reception.session
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    session["agenda_data"] = {"data": "2026-03-05", "em": ontem.isoformat()}
    session.save()
    assert reception.get(reverse("schedule:calendar")).context["configuracao"]["date"] == ""


def test_ficha_cadastral_impressa(clinica_a, reception):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(
            name="Paciente fictícia da ficha",
            tax_id="52998224725",
            whatsapp="48999990000",
            notes="Prefere manhã",
        )
        health_plan = HealthPlan.objects.create(name="Saúde Exemplo")
        MemberCard.objects.create(patient=patient, health_plan=health_plan, number="123456")
    ficha = reception.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert reverse("patients:print", args=[patient.pk]) in ficha
    page = reception.get(reverse("patients:print", args=[patient.pk]))
    text = page.content.decode()
    for trecho in (
        "FICHA CADASTRAL",
        "529.982.247-25",
        "(48) 99999-0000",
        "Saúde Exemplo",
        "Prefere manhã",
    ):
        assert trecho in text, trecho
    assert (
        AuditEntry.objects.filter(
            action=AuditEntry.Acao.VISUALIZAR, object_id=str(patient.pk)
        ).count()
        == 2
    )  # the record and the print


def test_ficha_impressa_respeita_permissao(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Paciente fictício sem acesso")
    sem_vinculo = cliente_de(criar_usuario("sem_vinculo_paridade"))
    assert sem_vinculo.get(reverse("patients:print", args=[patient.pk])).status_code in (
        302,
        403,
    )
