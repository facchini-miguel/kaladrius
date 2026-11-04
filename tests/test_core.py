import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import MODULOS_GERAIS, Papel
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db


def test_inicio_exige_login(client):
    resposta = client.get(reverse("home"))
    assert resposta.status_code == 302
    assert reverse("login") in resposta.url


def test_login_e_inicio(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    resposta = client.post(
        reverse("login"), {"username": "maria", "password": "senha-de-teste-123"}, follow=True
    )
    assert resposta.status_code == 200
    assert ", maria" in resposta.content.decode()


def test_rodape_mostra_autor_e_versao(client):
    conteudo = client.get(reverse("login")).content.decode()
    assert "Desenvolvido por Miguel Facchini" in conteudo
    assert "versão" in conteudo


def test_login_com_senha_errada(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    resposta = client.post(reverse("login"), {"username": "maria", "password": "errada"})
    assert resposta.status_code == 200
    assert "Usuário ou senha incorretos" in resposta.content.decode()


def test_senha_usa_argon2(django_user_model):
    user = django_user_model.objects.create_user(username="joao", password="senha-de-teste-123")
    assert user.password.startswith("argon2")


def test_criar_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("create_admin")
    admin = get_user_model().objects.get(username="admin")
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password("senha-forte-de-teste-123")

    # Running it again changes nothing
    call_command("create_admin")
    assert get_user_model().objects.filter(username="admin").count() == 1


def test_criar_admin_falha_se_existir(monkeypatch):
    # The Linux package's installer tells the user that the password typed was not used.
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("create_admin", "--fail-if-exists")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "outra-senha-forte-456")
    with pytest.raises(CommandError) as erro:
        call_command("create_admin", "--fail-if-exists")
    assert erro.value.returncode == 3
    assert get_user_model().objects.get(username="admin").check_password("senha-forte-de-teste-123")


@pytest.mark.parametrize("senha", ["curta1", "1234567890123", "password123"])
def test_criar_admin_recusa_senha_fraca(monkeypatch, senha):
    # The Linux package's installer shows the reasons and asks again (decision 140).
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", senha)
    with pytest.raises(CommandError):
        call_command("create_admin")
    assert not get_user_model().objects.filter(username="admin").exists()


def test_criar_admin_sem_senha(monkeypatch):
    monkeypatch.delenv("DJANGO_ADMIN_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("create_admin")


def test_logout_exige_post(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    assert client.get(reverse("logout")).status_code == 405
    client.post(reverse("logout"))
    assert client.get(reverse("home")).status_code == 302


def test_usuario_troca_a_propria_senha(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    assert "Trocar senha" in client.get(reverse("home")).content.decode()
    resposta = client.post(
        reverse("change_password"),
        {
            "old_password": "senha-de-teste-123",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
        follow=True,
    )
    assert "Senha alterada." in resposta.content.decode()
    user.refresh_from_db()
    assert user.check_password("outra-senha-forte-456")
    # The session stays open after the change.
    assert client.get(reverse("home")).status_code == 200


def test_troca_de_senha_exige_a_senha_atual(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    resposta = client.post(
        reverse("change_password"),
        {
            "old_password": "errada",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
    )
    assert resposta.status_code == 200
    user.refresh_from_db()
    assert user.check_password("senha-de-teste-123")


def test_sem_recuperacao_de_senha_por_email(client):
    # No e-mail is configured, so the reset pages would never deliver anything.
    assert client.get("/account/password_reset/").status_code == 404


def test_aviso_de_backup_atrasado_so_para_superusuario(client, django_user_model, settings):
    import datetime

    from django.utils import timezone

    from apps.core.models import Backup

    admin = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    comum = django_user_model.objects.create_user("ana", password="senha-de-teste-123")
    client.force_login(admin)
    # Development has no backups: no warning.
    settings.BACKUP_MONITORED = False
    assert "backup" not in client.get(reverse("home")).content.decode()
    # A server where no backup was ever recorded warns too.
    settings.BACKUP_MONITORED = True
    assert "Nenhum backup do banco foi registrado" in client.get(reverse("home")).content.decode()

    call_command("record_backup", "kaladrius-x.dump", "1024")
    assert Backup.objects.get().tamanho == 1024
    assert "backups diários pararam" not in client.get(reverse("home")).content.decode()

    Backup.objects.update(momento=timezone.now() - datetime.timedelta(hours=27))
    assert "backups diários pararam" in client.get(reverse("home")).content.decode()
    client.force_login(comum)
    assert "backups diários pararam" not in client.get(reverse("home")).content.decode()


# --- Clinic settings ---------------------------------------------------------------


def dados_clinica(**extra):
    return {
        "name": "Clínica Atualizada",
        "area": "odontologia",
        "documento": "",
        "email": "",
        "phone": "",
        "agenda_inicio": "08:00",
        "agenda_fim": "18:00",
        "moeda": "BRL",
        "agenda_intervalo": 30,
        "modulos_gerais": sorted(MODULOS_GERAIS),
        **extra,
    }


def test_admin_altera_configuracoes_da_clinica(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    assert "Configurações da clínica" in cliente.get(reverse("home")).content.decode()
    assert 'value="07:30"' in cliente.get(reverse("clinic_settings")).content.decode()
    resposta = cliente.post(
        reverse("clinic_settings"),
        dados_clinica(documento="11.222.333/0001-81", agenda_intervalo=15),
    )
    assert resposta.status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.name, clinica_a.documento) == ("Clínica Atualizada", "11222333000181")
    assert (clinica_a.agenda_inicio, clinica_a.agenda_intervalo) == (datetime.time(8), 15)


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_o_admin_altera_configuracoes(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    assert cliente.get(reverse("clinic_settings")).status_code == 403


@pytest.mark.parametrize(
    ("extra", "erro"),
    [
        ({"agenda_inicio": "18:00", "agenda_fim": "08:00"}, "depois do início"),
        ({"documento": "123"}, "CPF/CNPJ: número inválido"),
        ({"agenda_inicio": "10:00"}, "ficaria fora do novo horário"),  # 09:00 appointment
        ({"agenda_intervalo": 60, "agenda_inicio": "08:30"}, "ficaria fora"),  # misaligned
    ],
)
def test_configuracoes_invalidas(extra, erro, clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        practitioner = Practitioner.objects.create(name="Dra. Teste")
        tipo = AppointmentType.objects.first()
        amanha = timezone.localdate() + datetime.timedelta(days=1)
        inicio = timezone.make_aware(datetime.datetime.combine(amanha, datetime.time(9)))
        Appointment.objects.create(
            practitioner=practitioner,
            tipo=tipo,
            inicio=inicio,
            fim=inicio + datetime.timedelta(hours=1),
        )
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    resposta = cliente.post(reverse("clinic_settings"), dados_clinica(**extra))
    assert resposta.status_code == 200
    assert erro in resposta.content.decode()


def test_todo_app_declara_o_proprio_label():
    """Without one, Django takes the folder's name for the label, and renaming the folder would
    leave the database's tables behind (decision 154: the account app, ex-conta)."""
    from django.apps import apps

    for config in apps.get_app_configs():
        if config.name.startswith("apps."):
            assert "label" in type(config).__dict__, config.name
