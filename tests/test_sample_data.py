import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db.models import F

from apps.audit.models import AuditEntry
from apps.core.isolation import without_isolation
from apps.core.models import Clinic, Membership, Role
from apps.core.validators import valid_cnpj, valid_cpf
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule.models import Appointment

pytestmark = pytest.mark.django_db


def test_populate_sample_data_is_idempotent(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("seed_sample_data", patients=30)
    call_command("seed_sample_data", patients=30)

    # One installation, one clinic (decision 069).
    assert Clinic.objects.count() == 1
    assert get_user_model().objects.get(username="dr.carlos").check_password("senha-de-teste-123")
    assert Membership.objects.filter(user__username="dra.ana").count() == 1
    # One user per role, so every role can be tried (review stage 3).
    assert set(Membership.objects.values_list("role", flat=True)) == set(Role)
    with without_isolation():
        assert Practitioner.objects.count() == 5
        assert Practitioner.objects.get(name="Dra. Ana Souza").user.username == "dra.ana"
        assert Patient.objects.count() == 30  # not duplicated on the 2nd run
        assert Patient.objects.filter(kind=Patient.Kind.COMPANY).count() == 1
        for patient in Patient.objects.exclude(tax_id=""):
            is_valid = valid_cpf if patient.kind == Patient.Kind.INDIVIDUAL else valid_cnpj
            assert is_valid(patient.tax_id), patient.tax_id
        assert not Patient.objects.exclude(email__endswith="@example.com").exists()
        assert Appointment.objects.count() > 0  # created once, not duplicated
        assert Recall.objects.count() == 80  # not duplicated
        assert Appointment.objects.filter(practitioner__clinic=F("clinic")).count() == (
            Appointment.objects.count()
        )


def test_populate_sample_data_requires_debug(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    with pytest.raises(CommandError):
        call_command("seed_sample_data")


def test_remove_sample_data_does_not_touch_real_data(settings, monkeypatch, create_user):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("seed_sample_data", patients=5)
    real = Clinic.objects.create(name="Clínica Real")
    create_user("pessoa.real", real)
    # A test username that also works in a real clinic is kept.
    Membership.objects.create(user=get_user_model().objects.get(username="dra.ana"), clinic=real)
    with without_isolation():
        Patient.objects.create(clinic=real, name="Paciente Real")

    with pytest.raises(CommandError):
        call_command("remove_sample_data")
    call_command("remove_sample_data", confirm=True)

    assert list(Clinic.objects.values_list("name", flat=True)) == ["Clínica Real"]
    remaining = set(get_user_model().objects.values_list("username", flat=True))
    assert remaining == {"pessoa.real", "dra.ana"}
    with without_isolation():
        assert list(Patient.objects.values_list("name", flat=True)) == ["Paciente Real"]
        assert not Appointment.objects.exists() and not Recall.objects.exists()
        assert set(Practitioner.objects.values_list("clinic", flat=True)) <= {real.pk}
    assert not AuditEntry.objects.filter(object_repr__contains="(teste)").exists()
    assert AuditEntry.objects.filter(
        object_repr__startswith="Dados de teste removidos: 1 clínicas"
    ).exists()


def test_fake_occupation_fits_the_field_uncut():
    """Faker 40's pt_BR job list has titles over 100 characters: another one is drawn."""
    from apps.core import fake_data

    titles = iter(["Especialista " * 10, "Dentista"])

    class Fake:
        def job(self):
            return next(titles)

    assert fake_data.occupation(Fake()) == "Dentista"


def test_fake_document_always_valid():
    """Faker 40 can, rarely, make up a CPF with all digits equal: another one is drawn."""
    from apps.core import fake_data

    numbers = iter(["111.111.111-11", "529.982.247-25"])

    class Fake:
        def cpf(self):
            return next(numbers)

    assert fake_data.cpf(Fake()) == "52998224725"
