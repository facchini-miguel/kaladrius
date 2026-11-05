"""Interface languages (decision 049): Portuguese source, English and Spanish translations."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from apps.core.models import Role
from apps.whats_new import releases

pytestmark = pytest.mark.django_db

LOCALE = Path(settings.BASE_DIR) / "locale"


@pytest.fixture
def cliente(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("maria", clinica_a, Role.ADMIN))


def test_usuario_escolhe_o_idioma_e_a_escolha_fica_salva(cliente, django_user_model):
    start = reverse("home")
    assert "Pacientes" in cliente.get(start).content.decode()

    response = cliente.post(
        reverse("change_language"), {"language": "en", "next": start}, follow=True
    )
    page = response.content.decode()
    assert '<html lang="en">' in page
    assert "Patients" in page and "Recalls" in page and "Log out" in page
    assert django_user_model.objects.get(username="maria").language == "en"
    assert response.redirect_chain[-1][0] == start
    assert cliente.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"

    cliente.post(reverse("change_language"), {"language": "es"})
    page = cliente.get(reverse("patients:list")).content.decode()
    assert "Nuevo paciente" in page and "Recordatorios" in page

    # Empty (or unknown): back to the browser's language.
    cliente.post(reverse("change_language"), {"language": "klingon"})
    assert django_user_model.objects.get(username="maria").language == ""


def test_seletor_de_idioma_com_bandeiras_na_barra(cliente):
    page = cliente.get(reverse("home")).content.decode()
    for code in ("pt-br", "en", "es"):
        assert f"img/flags/{code}." in page  # CI serves hashed names (x.1a2b.svg)
    # Its own menu, before the user's menu (between the clinic and the user name).
    assert page.index("seletor-idioma") < page.index(reverse("change_password"))


def test_escolha_do_usuario_vale_mais_que_o_navegador(cliente, django_user_model):
    django_user_model.objects.filter(username="maria").update(language="es")
    page = cliente.get(reverse("home"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert any(saludo in page for saludo in ("Buenos días", "Buenas tardes", "Buenas noches"))


def test_login_segue_o_idioma_do_navegador(client):
    page = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="es").content.decode()
    assert "Contraseña" in page
    page = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9").content.decode()
    assert "Password" in page


def test_mensagens_e_erros_traduzidos(cliente, django_user_model):
    django_user_model.objects.filter(username="maria").update(language="en")
    response = cliente.post(reverse("patients:new"), {"kind": "PF", "name": "", "active": "on"})
    assert "This field is required." in response.content.decode()
    response = cliente.post(
        reverse("patients:new"), {"kind": "PF", "name": "Ana", "active": "on"}, follow=True
    )
    assert "Patient Ana saved." in response.content.decode()


def test_trocar_idioma_exige_post_e_login(client):
    assert client.get(reverse("change_language")).status_code in (302, 405)


@pytest.mark.parametrize("language", ["en", "es"])
def test_todos_os_textos_estao_traduzidos(language):
    po = (LOCALE / language / "LC_MESSAGES" / "django.po").read_text(encoding="utf-8")
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
    languages = {code for code, _nome in settings.LANGUAGES}
    for release in releases.todas():
        assert set(dict(release.titulos)) == languages or not release.titulo, release.versao
        for item in release.itens:
            assert set(dict(item.textos)) == languages, (release.versao, item.text)
            assert item.modulo in releases.MODULOS, item.modulo


def test_situacoes_em_aberto_concordam_em_espanhol():
    """One Portuguese "Em aberto", a different Spanish word for each thing it describes."""
    from django.utils import translation
    from django.utils.translation import pgettext

    from apps.estimates.models import Estimate

    with translation.override("es"):
        assert str(Estimate.Status.OPEN.label) == "Abierto"
        assert pgettext("parcela", "Em aberto") == "Abierta"
        assert pgettext("valor", "Em aberto") == "Pendiente"
    with translation.override("en"):
        assert str(Estimate.Status.OPEN.label) == "Open"


def test_horario_em_ingles_sem_ponto_duplo():
    """Django's "p.m." made a sentence ending in a time end with two periods."""
    import datetime

    from django.utils import translation
    from django.utils.formats import date_format

    timestamp = datetime.datetime(2026, 10, 31, 23, 15)
    with translation.override("en"):
        assert date_format(timestamp, "SHORT_DATETIME_FORMAT") == "10/31/2026 11:15 PM"
        assert date_format(timestamp, "TIME_FORMAT") == "11:15 PM"
    with translation.override("pt-br"):
        assert date_format(timestamp, "SHORT_DATETIME_FORMAT") == "31/10/2026 23:15"
