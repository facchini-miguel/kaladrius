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
