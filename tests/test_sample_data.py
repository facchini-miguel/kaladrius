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


def test_popular_dados_teste_e_idempotente(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("seed_sample_data", pacientes=30)
    call_command("seed_sample_data", pacientes=30)

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


def test_popular_dados_teste_exige_debug(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    with pytest.raises(CommandError):
        call_command("seed_sample_data")


def test_remover_dados_teste_nao_toca_nos_dados_reais(settings, monkeypatch, criar_usuario):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("seed_sample_data", pacientes=5)
    real = Clinic.objects.create(name="Clínica Real")
    criar_usuario("pessoa.real", real)
    # A test username that also works in a real clinic is kept.
    Membership.objects.create(user=get_user_model().objects.get(username="dra.ana"), clinic=real)
    with without_isolation():
        Patient.objects.create(clinic=real, name="Paciente Real")

    with pytest.raises(CommandError):
        call_command("remove_sample_data")
    call_command("remove_sample_data", confirmar=True)

    assert list(Clinic.objects.values_list("name", flat=True)) == ["Clínica Real"]
    restantes = set(get_user_model().objects.values_list("username", flat=True))
    assert restantes == {"pessoa.real", "dra.ana"}
    with without_isolation():
        assert list(Patient.objects.values_list("name", flat=True)) == ["Paciente Real"]
        assert not Appointment.objects.exists() and not Recall.objects.exists()
        assert set(Practitioner.objects.values_list("clinic", flat=True)) <= {real.pk}
    assert not AuditEntry.objects.filter(object_repr__contains="(teste)").exists()
    assert AuditEntry.objects.filter(
        object_repr__startswith="Dados de teste removidos: 1 clínicas"
    ).exists()


def test_profissao_ficticia_cabe_no_campo_sem_ser_cortada():
    """Faker 40's pt_BR job list has titles over 100 characters: another one is drawn."""
    from apps.core import fake_data

    titulos = iter(["Especialista " * 10, "Dentista"])

    class Falso:
        def job(self):
            return next(titulos)

    assert fake_data.occupation(Falso()) == "Dentista"


def test_documento_ficticio_sempre_valido():
    """Faker 40 can, rarely, make up a CPF with all digits equal: another one is drawn."""
    from apps.core import fake_data

    numeros = iter(["111.111.111-11", "529.982.247-25"])

    class Falso:
        def cpf(self):
            return next(numeros)

    assert fake_data.cpf(Falso()) == "52998224725"
