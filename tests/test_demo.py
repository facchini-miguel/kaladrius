import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Membership, Role
from apps.medical_records.models import Attachment, Visit
from apps.practitioners.models import Practitioner

from .test_medical_record import ANAMNESIS, PNG

PASSWORDS = {"senha_recepcao": "demo-recepcao-1", "senha_profissional": "demo-profissional-1"}


@pytest.fixture
def demo(clinic_a, create_practitioner, monkeypatch):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    bruno = create_practitioner(clinic_a, "Dr. Bruno")
    call_command("demo_accounts", clinic="Clínica A", practitioner="Dr. Bruno", **PASSWORDS)
    return {"clinic": clinic_a, "bruno": bruno}


def log_in(username, password):
    """Log in through the login page (axes needs a request), failing if the password is wrong."""
    user_client = Client()
    response = user_client.post(reverse("login"), {"username": username, "password": password})
    assert response.status_code == 302, response.content.decode()[:300]
    return user_client


def test_creates_both_accounts_with_their_roles(demo):
    User = get_user_model()
    reception = User.objects.get(username="demo.recepcao")
    practitioner = User.objects.get(username="demo.profissional")
    assert reception.demo and practitioner.demo
    assert not (reception.is_staff or reception.is_superuser)
    assert Membership.objects.get(user=reception).role == Role.FRONT_DESK
    assert Membership.objects.get(user=practitioner).role == Role.PRACTITIONER
    with use_clinic(demo["clinic"]):
        assert Practitioner.objects.get(name="Dr. Bruno").user == practitioner
    # Running again resets the passwords and keeps one link per clinic.
    call_command(
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dr. Bruno",
        senha_recepcao="outra-1",
        senha_profissional="outra-2",
    )
    assert Membership.objects.filter(user__username__startswith="demo.").count() == 2
    log_in("demo.recepcao", "outra-1")


def test_refuses_sample_data_password_and_practitioner_with_another_user(
    demo, create_user, clinic_a
):
    with pytest.raises(CommandError, match="DJANGO_SEED_PASSWORD"):
        call_command(
            "demo_accounts",
            clinic="Clínica A",
            practitioner="Dr. Bruno",
            senha_recepcao="semente-secreta",
            senha_profissional="x-1",
        )
    with use_clinic(clinic_a):
        Practitioner.objects.create(name="Dra. Ana", user=create_user("dra.ana"))
    with pytest.raises(CommandError, match="outro usuário"):
        call_command("demo_accounts", clinic="Clínica A", practitioner="Dra. Ana", **PASSWORDS)


def test_creates_the_practitioner_when_asked(clinic_a, monkeypatch):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    with pytest.raises(CommandError, match="--create-practitioner"):
        call_command("demo_accounts", clinic="Clínica A", practitioner="Dra. Demo", **PASSWORDS)
    call_command(
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dra. Demo",
        criar_profissional=True,
        **PASSWORDS,
    )
    call_command(  # running again reuses it
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dra. Demo",
        criar_profissional=True,
        **PASSWORDS,
    )
    with use_clinic(clinic_a):
        demo = Practitioner.objects.get(name="Dra. Demo")
    assert demo.user.username == "demo.profissional"


def test_demo_account_cannot_change_password(demo):
    user_client = log_in("demo.recepcao", PASSWORDS["senha_recepcao"])
    assert "Trocar senha" not in user_client.get(reverse("home")).content.decode()
    response = user_client.post(
        reverse("change_password"),
        {
            "old_password": PASSWORDS["senha_recepcao"],
            "new_password1": "Nova-senha-123!",
            "new_password2": "Nova-senha-123!",
        },
        follow=True,
    )
    assert "Contas de demonstração não trocam a senha." in response.content.decode()
    log_in("demo.recepcao", PASSWORDS["senha_recepcao"])


def test_demo_account_cannot_upload_attachments(demo):
    user_client = log_in("demo.profissional", PASSWORDS["senha_profissional"])
    with use_clinic(demo["clinic"]):
        from apps.patients.models import Patient

        patient = Patient.objects.create(name="Maria Paciente")
    user_client.post(reverse("medical_records:new", args=[patient.pk]), ANAMNESIS)
    with use_clinic(demo["clinic"]):
        visit = Visit.objects.get()
    page = user_client.get(reverse("medical_records:visit", args=[visit.pk])).content.decode()
    assert "Contas de demonstração não enviam anexos." in page
    assert "anexo_enviar" not in page and 'enctype="multipart/form-data"' not in page
    response = user_client.post(
        reverse("medical_records:attachment_upload", args=[visit.pk]),
        {"file": SimpleUploadedFile("x.png", PNG)},
        follow=True,
    )
    assert "Contas de demonstração não enviam anexos." in response.content.decode()
    with use_clinic(demo["clinic"]):
        assert not Attachment.objects.exists()


def test_demo_admin_and_finance_cannot_touch_team_or_clinic(
    clinic_a, create_practitioner, monkeypatch
):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    create_practitioner(clinic_a, "Dr. Bruno")
    call_command(
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dr. Bruno",
        senha_financeiro="demo-financeiro-1",
        senha_admin="demo-admin-1",
        **PASSWORDS,
    )
    assert Membership.objects.get(user__username="demo.financeiro").role == Role.FINANCE
    admin = log_in("demo.admin", "demo-admin-1")
    reception = get_user_model().objects.get(username="demo.recepcao")
    membership = Membership.objects.get(user=reception)
    # Sees the team, but cannot add members, edit them or reset their passwords.
    results = admin.get(reverse("team:list"))
    assert results.status_code == 200 and "Novo membro" not in results.content.decode()
    assert admin.get(reverse("team:new")).status_code == 403
    assert admin.post(reverse("team:password", args=[membership.pk]), {}).status_code == 403
    assert admin.get(reverse("clinic_settings")).status_code == 403
    # The audit log is there, without the visitors' IP addresses.
    audit = admin.get(reverse("audit:list")).content.decode()
    assert ">IP<" not in audit
    # Everything else of an administrator still works (finance, for example).
    assert admin.get(reverse("finance:payables")).status_code == 200
    log_in("demo.financeiro", "demo-financeiro-1").get(reverse("finance:cash_flow"))
