"""Interface languages (decision 049): Portuguese source, English and Spanish translations."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from apps.core.models import Papel
from apps.novidades import releases

pytestmark = pytest.mark.django_db

LOCALE = Path(settings.BASE_DIR) / "locale"


@pytest.fixture
def cliente(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("maria", clinica_a, Papel.ADMIN))


def test_usuario_escolhe_o_idioma_e_a_escolha_fica_salva(cliente, django_user_model):
    inicio = reverse("inicio")
    assert "Pacientes" in cliente.get(inicio).content.decode()

    resposta = cliente.post(reverse("trocar_idioma"), {"idioma": "en", "next": inicio}, follow=True)
    pagina = resposta.content.decode()
    assert '<html lang="en">' in pagina
    assert "Patients" in pagina and "Recalls" in pagina and "Log out" in pagina
    assert django_user_model.objects.get(username="maria").idioma == "en"
    assert resposta.redirect_chain[-1][0] == inicio
    assert cliente.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"

    cliente.post(reverse("trocar_idioma"), {"idioma": "es"})
    pagina = cliente.get(reverse("pacientes:lista")).content.decode()
    assert "Nuevo paciente" in pagina and "Recordatorios" in pagina

    # Empty (or unknown): back to the browser's language.
    cliente.post(reverse("trocar_idioma"), {"idioma": "klingon"})
    assert django_user_model.objects.get(username="maria").idioma == ""


def test_seletor_de_idioma_com_bandeiras_na_barra(cliente):
    pagina = cliente.get(reverse("inicio")).content.decode()
    for codigo in ("pt-br", "en", "es"):
        assert f"img/bandeiras/{codigo}." in pagina  # CI serves hashed names (x.1a2b.svg)
    # Its own menu, before the user's menu (between the clinic and the user name).
    assert pagina.index("seletor-idioma") < pagina.index(reverse("trocar_senha"))


def test_escolha_do_usuario_vale_mais_que_o_navegador(cliente, django_user_model):
    django_user_model.objects.filter(username="maria").update(idioma="es")
    pagina = cliente.get(reverse("inicio"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Bienvenido(a)" in pagina


def test_login_segue_o_idioma_do_navegador(client):
    pagina = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="es").content.decode()
    assert "Contraseña" in pagina
    pagina = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9").content.decode()
    assert "Password" in pagina


def test_mensagens_e_erros_traduzidos(cliente, django_user_model):
    django_user_model.objects.filter(username="maria").update(idioma="en")
    resposta = cliente.post(reverse("pacientes:novo"), {"tipo": "PF", "nome": "", "ativo": "on"})
    assert "This field is required." in resposta.content.decode()
    resposta = cliente.post(
        reverse("pacientes:novo"), {"tipo": "PF", "nome": "Ana", "ativo": "on"}, follow=True
    )
    assert "Patient Ana saved." in resposta.content.decode()


def test_trocar_idioma_exige_post_e_login(client):
    assert client.get(reverse("trocar_idioma")).status_code in (302, 405)


@pytest.mark.parametrize("idioma", ["en", "es"])
def test_todos_os_textos_estao_traduzidos(idioma):
    po = (LOCALE / idioma / "LC_MESSAGES" / "django.po").read_text(encoding="utf-8")
    blocos = po.split("\n\n")[1:]
    # Long translations are wrapped: msgstr "" followed by "..." lines, so join them first.
    sem_traducao = [
        bloco
        for bloco in blocos
        for traducao in re.findall(r'^msgstr(?:\[\d\])? ((?:".*"\n?)+)', bloco, re.M)
        if not "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', traducao))
    ]
    assert not sem_traducao, sem_traducao[:3]
    assert "#, fuzzy" not in po


def test_novidades_nos_tres_idiomas():
    idiomas = {codigo for codigo, _nome in settings.LANGUAGES}
    for release in releases.todas():
        assert set(dict(release.titulos)) == idiomas or not release.titulo, release.versao
        for item in release.itens:
            assert set(dict(item.textos)) == idiomas, (release.versao, item.texto)
            assert item.modulo in releases.MODULOS, item.modulo
