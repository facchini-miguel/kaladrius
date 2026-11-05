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

from .test_medical_record import ANAMNESE, PNG

SENHAS = {"senha_recepcao": "demo-recepcao-1", "senha_profissional": "demo-profissional-1"}


@pytest.fixture
def demo(clinica_a, criar_profissional, monkeypatch):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    call_command("demo_accounts", clinic="Clínica A", practitioner="Dr. Bruno", **SENHAS)
    return {"clinic": clinica_a, "bruno": bruno}


def entrar(username, password):
    """Log in through the login page (axes needs a request), failing if the password is wrong."""
    cliente = Client()
    response = cliente.post(reverse("login"), {"username": username, "password": password})
    assert response.status_code == 302, response.content.decode()[:300]
    return cliente


def test_cria_as_duas_contas_com_os_perfis(demo):
    Usuario = get_user_model()
    reception = Usuario.objects.get(username="demo.recepcao")
    practitioner = Usuario.objects.get(username="demo.profissional")
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
    entrar("demo.recepcao", "outra-1")


def test_recusa_a_senha_dos_dados_de_teste_e_profissional_com_outro_usuario(
    demo, criar_usuario, clinica_a
):
    with pytest.raises(CommandError, match="DJANGO_SEED_PASSWORD"):
        call_command(
            "demo_accounts",
            clinic="Clínica A",
            practitioner="Dr. Bruno",
            senha_recepcao="semente-secreta",
            senha_profissional="x-1",
        )
    with use_clinic(clinica_a):
        Practitioner.objects.create(name="Dra. Ana", user=criar_usuario("dra.ana"))
    with pytest.raises(CommandError, match="outro usuário"):
        call_command("demo_accounts", clinic="Clínica A", practitioner="Dra. Ana", **SENHAS)


def test_cria_o_profissional_quando_pedido(clinica_a, monkeypatch):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    with pytest.raises(CommandError, match="--create-practitioner"):
        call_command("demo_accounts", clinic="Clínica A", practitioner="Dra. Demo", **SENHAS)
    call_command(
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dra. Demo",
        criar_profissional=True,
        **SENHAS,
    )
    call_command(  # running again reuses it
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dra. Demo",
        criar_profissional=True,
        **SENHAS,
    )
    with use_clinic(clinica_a):
        demo = Practitioner.objects.get(name="Dra. Demo")
    assert demo.user.username == "demo.profissional"


def test_conta_de_demonstracao_nao_troca_a_senha(demo):
    cliente = entrar("demo.recepcao", SENHAS["senha_recepcao"])
    assert "Trocar senha" not in cliente.get(reverse("home")).content.decode()
    response = cliente.post(
        reverse("change_password"),
        {
            "old_password": SENHAS["senha_recepcao"],
            "new_password1": "Nova-senha-123!",
            "new_password2": "Nova-senha-123!",
        },
        follow=True,
    )
    assert "Contas de demonstração não trocam a senha." in response.content.decode()
    entrar("demo.recepcao", SENHAS["senha_recepcao"])


def test_conta_de_demonstracao_nao_envia_anexos(demo):
    cliente = entrar("demo.profissional", SENHAS["senha_profissional"])
    with use_clinic(demo["clinic"]):
        from apps.patients.models import Patient

        patient = Patient.objects.create(name="Maria Paciente")
    cliente.post(reverse("medical_records:new", args=[patient.pk]), ANAMNESE)
    with use_clinic(demo["clinic"]):
        visit = Visit.objects.get()
    page = cliente.get(reverse("medical_records:visit", args=[visit.pk])).content.decode()
    assert "Contas de demonstração não enviam anexos." in page
    assert "anexo_enviar" not in page and 'enctype="multipart/form-data"' not in page
    response = cliente.post(
        reverse("medical_records:attachment_upload", args=[visit.pk]),
        {"file": SimpleUploadedFile("x.png", PNG)},
        follow=True,
    )
    assert "Contas de demonstração não enviam anexos." in response.content.decode()
    with use_clinic(demo["clinic"]):
        assert not Attachment.objects.exists()


def test_admin_e_financeiro_de_demonstracao_nao_mexem_na_equipe_nem_na_clinica(
    clinica_a, criar_profissional, monkeypatch
):
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "semente-secreta")
    criar_profissional(clinica_a, "Dr. Bruno")
    call_command(
        "demo_accounts",
        clinic="Clínica A",
        practitioner="Dr. Bruno",
        senha_financeiro="demo-financeiro-1",
        senha_admin="demo-admin-1",
        **SENHAS,
    )
    assert Membership.objects.get(user__username="demo.financeiro").role == Role.FINANCE
    admin = entrar("demo.admin", "demo-admin-1")
    reception = get_user_model().objects.get(username="demo.recepcao")
    vinculo = Membership.objects.get(user=reception)
    # Sees the team, but cannot add members, edit them or reset their passwords.
    results = admin.get(reverse("team:list"))
    assert results.status_code == 200 and "Novo membro" not in results.content.decode()
    assert admin.get(reverse("team:new")).status_code == 403
    assert admin.post(reverse("team:password", args=[vinculo.pk]), {}).status_code == 403
    assert admin.get(reverse("clinic_settings")).status_code == 403
    # The audit log is there, without the visitors' IP addresses.
    auditoria = admin.get(reverse("audit:list")).content.decode()
    assert ">IP<" not in auditoria
    # Everything else of an administrator still works (finance, for example).
    assert admin.get(reverse("finance:payables")).status_code == 200
    entrar("demo.financeiro", "demo-financeiro-1").get(reverse("finance:cash_flow"))
