"""Small habits of the legacy systems: the schedule remembers the week, and the patient
registration sheet prints (legacy Medical fichapaciente_imp). Fictitious data only."""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


@pytest.fixture
def reception(clinic_a, create_user, client_for):
    return client_for(create_user("recepcao_paridade", clinic_a, Role.FRONT_DESK))


def test_schedule_returns_to_the_week_that_was_open(clinic_a, reception, create_practitioner):
    practitioner = create_practitioner(clinic_a, "Profissional fictício")
    week = {"start": "2026-03-02T00:00:00", "end": "2026-03-09T00:00:00"}
    event_list = reception.get(
        reverse("schedule:events"), {**week, "practitioner": practitioner.pk}
    )
    assert event_list.status_code == 200
    config = reception.get(reverse("schedule:calendar")).context["schedule_settings"]
    assert config["date"] == "2026-03-05"  # middle of the week on the screen
    # An explicit date still wins.
    explicit = reception.get(reverse("schedule:calendar"), {"date": "2026-04-01"})
    assert explicit.context["schedule_settings"]["date"] == "2026-04-01"


def test_next_day_schedule_opens_today(reception):
    session = reception.session
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    session["agenda_data"] = {"data": "2026-03-05", "em": yesterday.isoformat()}
    session.save()
    assert reception.get(reverse("schedule:calendar")).context["schedule_settings"]["date"] == ""


def test_printed_registration_record(clinic_a, reception):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(
            name="Paciente fictícia da ficha",
            tax_id="52998224725",
            whatsapp="48999990000",
            notes="Prefere manhã",
        )
        health_plan = HealthPlan.objects.create(name="Saúde Exemplo")
        MemberCard.objects.create(patient=patient, health_plan=health_plan, number="123456")
    patient_record = reception.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert reverse("patients:print", args=[patient.pk]) in patient_record
    page = reception.get(reverse("patients:print", args=[patient.pk]))
    text = page.content.decode()
    for excerpt in (
        "FICHA CADASTRAL",
        "529.982.247-25",
        "(48) 99999-0000",
        "Saúde Exemplo",
        "Prefere manhã",
    ):
        assert excerpt in text, excerpt
    assert (
        AuditEntry.objects.filter(
            action=AuditEntry.Action.VIEWED, object_id=str(patient.pk)
        ).count()
        == 2
    )  # the record and the print


def test_printed_record_respects_permission(clinic_a, create_user, client_for):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paciente fictício sem acesso")
    without_membership = client_for(create_user("sem_vinculo_paridade"))
    assert without_membership.get(reverse("patients:print", args=[patient.pk])).status_code in (
        302,
        403,
    )
