"""The stored choice values follow the running code's, in either direction (decision 197): after
`migrate`, the versions before and after the English values work on the same database."""

import datetime

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.utils import timezone, translation

from apps.audit.models import AuditEntry
from apps.audit.views import changed_fields
from apps.core.isolation import use_clinic
from apps.core.models import ClinicModule, ModuleCode
from apps.core.values import VALUES, direction, field_pairs, sync_values
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# Choice fields whose values are already codes anyone reads: standards and letters.
STANDARD = {
    "core.User.language",
    "core.Clinic.currency",
    "core.Clinic.country",
    "core.Clinic.time_zone",
    "core.Clinic.tooth_numbering",
    "core.Clinic.schedule_interval",
    "patients.Patient.sex",
}


def choice_fields():
    for model in apps.get_models():
        if model.__module__.startswith("apps."):
            for field in model._meta.fields:
                if field.choices:
                    yield f"{model._meta.label}.{field.name}", model, field


def test_every_choice_field_is_in_the_map_or_a_standard():
    keys = {key for key, _model, _field in choice_fields()}
    assert keys - STANDARD == set(VALUES)


def enums(cls=None):
    from django.db import models

    for sub in (cls or models.TextChoices).__subclasses__():
        yield sub
        yield from enums(sub)


@pytest.mark.parametrize("key", sorted(VALUES))
def test_each_english_value_is_its_members_name(key):
    _label, model, field = next(item for item in choice_fields() if item[0] == key)
    mapping = VALUES[key]
    values = {value for value, _text in field.choices}
    names = {}
    for enum in enums():
        if set(enum.values) == values:
            names.update({member.value: member.name.lower() for member in enum})
    assert names, key
    for value in values:
        english = mapping.get(value, value)
        assert english == names[value], (key, value)
        assert len(english) <= field.max_length, (key, english)
    assert not set(mapping) & set(mapping.values()), key  # one spelling never reads as the other


def test_direction_follows_the_code():
    mapping = {"agendado": "booked", "faltou": "missed"}
    assert direction(mapping, ["agendado", "faltou"]) == {"booked": "agendado", "missed": "faltou"}
    assert direction(mapping, ["booked", "missed"]) == mapping


def other_spelling(field_key, value):
    """The value as the version on the other side of decision 197 stores it."""
    mapping = VALUES[field_key]
    return mapping.get(value) or {e: p for p, e in mapping.items()}[value]


@pytest.fixture
def appointment(clinic_a):
    with use_clinic(clinic_a):
        start = timezone.make_aware(datetime.datetime(2026, 11, 9, 9))
        return Appointment.objects.create(
            practitioner=Practitioner.objects.create(name="Dra. Teste"),
            kind=AppointmentType.objects.first(),
            start=start,
            end=start + datetime.timedelta(hours=1),
            status=Appointment.Status.ATTENDED,
        )


def test_migrate_converts_the_other_spelling(appointment, clinic_a):
    status = Appointment.Status.ATTENDED.value
    module = ClinicModule._base_manager.filter(clinic=clinic_a).first()
    code = module.code
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_appointment SET status = %s WHERE id = %s",
            [other_spelling("schedule.Appointment.status", status), appointment.pk],
        )
        cursor.execute(
            "UPDATE core_clinic_module SET code = %s WHERE id = %s",
            [other_spelling("core.ClinicModule.code", code), module.pk],
        )

    call_command("migrate", verbosity=0, stdout=open("/dev/null", "w"))

    appointment.refresh_from_db()
    module.refresh_from_db()
    assert (appointment.status, module.code) == (status, code)
    assert sync_values() == []  # nothing left to convert


def test_migrate_of_one_app_leaves_the_values(appointment):
    """An older state (tests migrating back) keeps the values its migrations expect."""
    status = Appointment.Status.ATTENDED.value
    old = other_spelling("schedule.Appointment.status", status)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_appointment SET status = %s WHERE id = %s", [old, appointment.pk]
        )
    call_command("migrate", "schedule", verbosity=0)
    appointment.refresh_from_db()
    assert appointment.status == old
    sync_values()


def test_every_field_converts_both_ways():
    for _model, field, pairs in field_pairs():
        assert pairs, field
    changed = sync_values()
    assert changed == []


def test_module_check_accepts_both_spellings(clinic_a):
    module = ClinicModule._base_manager.filter(clinic=clinic_a, code=ModuleCode.SCHEDULE).first()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE core_clinic_module SET code = %s WHERE id = %s",
            [other_spelling("core.ClinicModule.code", ModuleCode.SCHEDULE.value), module.pk],
        )
    sync_values()
    module.refresh_from_db()
    assert module.code == ModuleCode.SCHEDULE


def test_audit_shows_the_label_of_either_spelling(appointment):
    entry = AuditEntry.objects.filter(object_id=str(appointment.pk)).latest("pk")
    status = Appointment.Status.ATTENDED.value
    entry.changes = {"status": [other_spelling("schedule.Appointment.status", status), status]}
    with translation.override("pt-br"):
        shown = {label: (before, after) for label, before, after in changed_fields(entry)}
        assert [(str(b), str(a)) for b, a in shown.values()] == [("Compareceu", "Compareceu")]
    # An old entry's Portuguese field name, and a value no choice has, stay as stored.
    entry.changes = {"situacao": ["faltou", "?"]}
    with translation.override("pt-br"):
        ((_label, before, after),) = changed_fields(entry)
        assert (str(before), after) == ("Faltou", "?")


def test_a_cancelled_appointment_frees_the_slot_in_either_spelling(appointment, clinic_a):
    """The no-overlap constraint must hold while rows are converted, both ways."""
    cancelled = Appointment.Status.CANCELLED.value
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE schedule_appointment SET status = %s WHERE id = %s",
            [other_spelling("schedule.Appointment.status", cancelled), appointment.pk],
        )
    with use_clinic(clinic_a):
        Appointment.objects.create(
            practitioner=appointment.practitioner,
            kind=appointment.kind,
            start=appointment.start,
            end=appointment.end,
        )
    sync_values()  # both now in the code's spelling: the cancelled one still frees the slot
    appointment.refresh_from_db()
    assert appointment.status == cancelled
