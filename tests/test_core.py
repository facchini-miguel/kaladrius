import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import GENERAL_MODULES, Role
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db


def test_home_requires_login(client):
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert reverse("login") in response.url


def test_login_and_home(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    response = client.post(
        reverse("login"), {"username": "maria", "password": "senha-de-teste-123"}, follow=True
    )
    assert response.status_code == 200
    assert ", maria" in response.content.decode()


def test_footer_shows_author_and_version(client):
    content = client.get(reverse("login")).content.decode()
    assert "Desenvolvido por Miguel Facchini" in content
    assert "versão" in content


def test_login_with_wrong_password(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    response = client.post(reverse("login"), {"username": "maria", "password": "errada"})
    assert response.status_code == 200
    assert "Usuário ou senha incorretos" in response.content.decode()


def test_password_uses_argon2(django_user_model):
    user = django_user_model.objects.create_user(username="joao", password="senha-de-teste-123")
    assert user.password.startswith("argon2")


def test_create_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("create_admin")
    admin = get_user_model().objects.get(username="admin")
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password("senha-forte-de-teste-123")

    # Running it again changes nothing
    call_command("create_admin")
    assert get_user_model().objects.filter(username="admin").count() == 1


def test_create_admin_fails_if_exists(monkeypatch):
    # The Linux package's installer tells the user that the password typed was not used.
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("create_admin", "--fail-if-exists")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "outra-senha-forte-456")
    with pytest.raises(CommandError) as error:
        call_command("create_admin", "--fail-if-exists")
    assert error.value.returncode == 3
    assert get_user_model().objects.get(username="admin").check_password("senha-forte-de-teste-123")


@pytest.mark.parametrize("password", ["curta1", "1234567890123", "password123"])
def test_create_admin_refuses_weak_password(monkeypatch, password):
    # The Linux package's installer shows the reasons and asks again (decision 140).
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", password)
    with pytest.raises(CommandError):
        call_command("create_admin")
    assert not get_user_model().objects.filter(username="admin").exists()


def test_create_admin_without_password(monkeypatch):
    monkeypatch.delenv("DJANGO_ADMIN_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("create_admin")


def test_logout_requires_post(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    assert client.get(reverse("logout")).status_code == 405
    client.post(reverse("logout"))
    assert client.get(reverse("home")).status_code == 302


def test_user_changes_own_password(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    assert "Trocar senha" in client.get(reverse("home")).content.decode()
    response = client.post(
        reverse("change_password"),
        {
            "old_password": "senha-de-teste-123",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
        follow=True,
    )
    assert "Senha alterada." in response.content.decode()
    user.refresh_from_db()
    assert user.check_password("outra-senha-forte-456")
    # The session stays open after the change.
    assert client.get(reverse("home")).status_code == 200


def test_password_change_requires_current_password(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    response = client.post(
        reverse("change_password"),
        {
            "old_password": "errada",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("senha-de-teste-123")


def test_no_password_recovery_by_email(client):
    # No e-mail is configured, so the reset pages would never deliver anything.
    assert client.get("/account/password_reset/").status_code == 404


def test_late_backup_warning_only_for_superuser(client, django_user_model, settings):
    import datetime

    from django.utils import timezone

    from apps.core.models import Backup

    admin = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    shared = django_user_model.objects.create_user("ana", password="senha-de-teste-123")
    client.force_login(admin)
    # Development has no backups: no warning.
    settings.BACKUP_MONITORED = False
    assert "backup" not in client.get(reverse("home")).content.decode()
    # A server where no backup was ever recorded warns too.
    settings.BACKUP_MONITORED = True
    assert "Nenhum backup do banco foi registrado" in client.get(reverse("home")).content.decode()

    call_command("record_backup", "kaladrius-x.dump", "1024")
    assert Backup.objects.get().size == 1024
    assert "backups diários pararam" not in client.get(reverse("home")).content.decode()

    Backup.objects.update(timestamp=timezone.now() - datetime.timedelta(hours=27))
    assert "backups diários pararam" in client.get(reverse("home")).content.decode()
    client.force_login(shared)
    assert "backups diários pararam" not in client.get(reverse("home")).content.decode()


# --- Clinic settings ---------------------------------------------------------------


def clinic_data(**extra):
    return {
        "name": "Clínica Atualizada",
        "area": "odontologia",
        "document": "",
        "email": "",
        "phone": "",
        "schedule_start": "08:00",
        "schedule_end": "18:00",
        "currency": "BRL",
        "schedule_interval": 30,
        "general_modules": sorted(GENERAL_MODULES),
        **extra,
    }


def test_admin_changes_clinic_settings(clinic_a, create_user, client_for):
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    assert "Configurações da clínica" in user_client.get(reverse("home")).content.decode()
    assert 'value="07:30"' in user_client.get(reverse("clinic_settings")).content.decode()
    response = user_client.post(
        reverse("clinic_settings"),
        clinic_data(document="11.222.333/0001-81", schedule_interval=15),
    )
    assert response.status_code == 302
    clinic_a.refresh_from_db()
    assert (clinic_a.name, clinic_a.document) == ("Clínica Atualizada", "11222333000181")
    assert (clinic_a.schedule_start, clinic_a.schedule_interval) == (datetime.time(8), 15)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_only_admin_changes_settings(role, clinic_a, create_user, client_for):
    user_client = client_for(create_user("usuario", clinic_a, role))
    assert user_client.get(reverse("clinic_settings")).status_code == 403


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        ({"schedule_start": "18:00", "schedule_end": "08:00"}, "depois do início"),
        ({"document": "123"}, "CPF/CNPJ: número inválido"),
        ({"schedule_start": "10:00"}, "ficaria fora do novo horário"),  # 09:00 appointment
        ({"schedule_interval": 60, "schedule_start": "08:30"}, "ficaria fora"),  # misaligned
    ],
)
def test_invalid_settings(extra, error, clinic_a, create_user, client_for):
    with use_clinic(clinic_a):
        practitioner = Practitioner.objects.create(name="Dra. Teste")
        kind = AppointmentType.objects.first()
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        start = timezone.make_aware(datetime.datetime.combine(tomorrow, datetime.time(9)))
        Appointment.objects.create(
            practitioner=practitioner,
            kind=kind,
            start=start,
            end=start + datetime.timedelta(hours=1),
        )
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    response = user_client.post(reverse("clinic_settings"), clinic_data(**extra))
    assert response.status_code == 200
    assert error in response.content.decode()


def test_every_app_declares_its_own_label():
    """Without one, Django takes the folder's name for the label, and renaming the folder would
    leave the database's tables behind (decision 154: the account app, ex-conta)."""
    from django.apps import apps

    for config in apps.get_app_configs():
        if config.name.startswith("apps."):
            assert "label" in type(config).__dict__, config.name
