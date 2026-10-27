import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_inicio_exige_login(client):
    resposta = client.get(reverse("inicio"))
    assert resposta.status_code == 302
    assert reverse("login") in resposta.url


def test_login_e_inicio(client, django_user_model):
    django_user_model.objects.create_user(username="maria", password="senha-de-teste-123")
    resposta = client.post(
        reverse("login"), {"username": "maria", "password": "senha-de-teste-123"}, follow=True
    )
    assert resposta.status_code == 200
    assert "Bem-vindo(a), maria" in resposta.content.decode()


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
    usuario = django_user_model.objects.create_user(username="joao", password="senha-de-teste-123")
    assert usuario.password.startswith("argon2")


def test_criar_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "senha-forte-de-teste-123")
    call_command("criar_admin")
    admin = get_user_model().objects.get(username="admin")
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password("senha-forte-de-teste-123")

    # Running it again changes nothing
    call_command("criar_admin")
    assert get_user_model().objects.filter(username="admin").count() == 1


def test_criar_admin_sem_senha(monkeypatch):
    monkeypatch.delenv("DJANGO_ADMIN_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("criar_admin")


def test_logout_exige_post(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    assert client.get(reverse("logout")).status_code == 405
    client.post(reverse("logout"))
    assert client.get(reverse("inicio")).status_code == 302


def test_usuario_troca_a_propria_senha(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    assert "Trocar senha" in client.get(reverse("inicio")).content.decode()
    resposta = client.post(
        reverse("trocar_senha"),
        {
            "old_password": "senha-de-teste-123",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
        follow=True,
    )
    assert "Senha alterada." in resposta.content.decode()
    usuario.refresh_from_db()
    assert usuario.check_password("outra-senha-forte-456")
    # The session stays open after the change.
    assert client.get(reverse("inicio")).status_code == 200


def test_troca_de_senha_exige_a_senha_atual(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    resposta = client.post(
        reverse("trocar_senha"),
        {
            "old_password": "errada",
            "new_password1": "outra-senha-forte-456",
            "new_password2": "outra-senha-forte-456",
        },
    )
    assert resposta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.check_password("senha-de-teste-123")


def test_sem_recuperacao_de_senha_por_email(client):
    # No e-mail is configured, so the reset pages would never deliver anything.
    assert client.get("/conta/password_reset/").status_code == 404


def test_aviso_de_backup_atrasado_so_para_superusuario(client, django_user_model):
    import datetime

    from django.utils import timezone

    from apps.core.models import Backup

    admin = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    comum = django_user_model.objects.create_user("ana", password="senha-de-teste-123")
    client.force_login(admin)
    # Development never records backups: no warning.
    assert "backups diários pararam" not in client.get(reverse("inicio")).content.decode()

    call_command("registrar_backup", "medical-system-x.dump", "1024")
    assert Backup.objects.get().tamanho == 1024
    assert "backups diários pararam" not in client.get(reverse("inicio")).content.decode()

    Backup.objects.update(momento=timezone.now() - datetime.timedelta(hours=27))
    assert "backups diários pararam" in client.get(reverse("inicio")).content.decode()
    client.force_login(comum)
    assert "backups diários pararam" not in client.get(reverse("inicio")).content.decode()
