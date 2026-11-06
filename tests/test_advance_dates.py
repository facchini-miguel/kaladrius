import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.patients.models import Patient
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType


@pytest.fixture
def scenario(clinic_a, create_practitioner):
    today = timezone.localdate()
    ana = create_practitioner(clinic_a, "Dra. Ana")
    with use_clinic(clinic_a):
        patient = Patient.objects.create(
            name="Maria Paciente", birth_date=datetime.date(1980, 5, 17)
        )
        kind = AppointmentType.objects.first()
        # Same time, one week apart: moving one week at a time row by row would overlap.
        week = [
            Appointment.objects.create(
                practitioner=ana,
                kind=kind,
                patient=patient,
                start=agenda.timestamp(today - datetime.timedelta(days=d), datetime.time(9)),
                end=agenda.timestamp(today - datetime.timedelta(days=d), datetime.time(10)),
            )
            for d in (21, 14)
        ]
        recall = Recall.objects.create(
            patient=patient, date=today - datetime.timedelta(days=20), description="Limpeza"
        )
    return {"clinic": clinic_a, "patient": patient, "schedule": week, "rechamada": recall}


def test_only_on_the_demo_server(scenario, settings):
    settings.DEMO = False
    with pytest.raises(CommandError, match="DJANGO_DEMO"):
        call_command("advance_dates", desde="2026-01-01", confirmar=True)
    settings.DEMO = True
    with pytest.raises(CommandError, match="--confirm"):
        call_command("advance_dates", desde="2026-01-01")


def test_advances_whole_weeks_and_keeps_birth_dates(scenario, settings):
    settings.DEMO = True
    today = timezone.localdate()
    before = {a.pk: (a.start, a.end) for a in scenario["schedule"]}
    # 17 days ago: two whole weeks, so each appointment keeps its weekday.
    call_command("advance_dates", desde=str(today - datetime.timedelta(days=17)), confirmar=True)
    with use_clinic(scenario["clinic"]):
        for appointment in Appointment.objects.all():
            start, end = before[appointment.pk]
            assert appointment.start - start == datetime.timedelta(days=14)
            assert appointment.end - end == datetime.timedelta(days=14)
            assert appointment.start.weekday() == start.weekday()
        assert Recall.objects.get().date == today - datetime.timedelta(days=6)
        assert Patient.objects.get().birth_date == datetime.date(1980, 5, 17)
        # The no-double-booking constraint is back.
        with pytest.raises(Exception, match="appointment_no_overlap"):
            first = Appointment.objects.first()
            Appointment.objects.create(
                practitioner=first.practitioner,
                kind=first.kind,
                start=first.start,
                end=first.end,
            )


def test_less_than_a_week_changes_nothing(scenario, settings):
    settings.DEMO = True
    today = timezone.localdate()
    call_command("advance_dates", desde=str(today - datetime.timedelta(days=6)), confirmar=True)
    with use_clinic(scenario["clinic"]):
        assert Recall.objects.get().date == today - datetime.timedelta(days=20)


def test_the_fixed_dates_exist():
    """A field renamed without updating FIXAS would silently start to move (a birth date)."""
    from django.apps import apps

    from apps.core.management.commands.advance_dates import FIXED

    for name in FIXED:
        label, template_, field = name.split(".")
        model_field = apps.get_model(label, template_)._meta.get_field(field)
        assert model_field.get_internal_type() in ("DateField", "DateTimeField"), name
