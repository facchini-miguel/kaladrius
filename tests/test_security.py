"""Login brute-force protection (django-axes), the "new version" notice and the CSP."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.novidades import releases

pytestmark = pytest.mark.django_db


def tentar(client, senha):
    return client.post(reverse("login"), {"username": "maria", "password": senha})


def test_bloqueia_apos_5_senhas_erradas(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200
    resposta = tentar(client, "errada")
    assert resposta.status_code == 429
    assert "bloqueado temporariamente" in resposta.content.decode()
    # Even the right password is refused while locked out.
    assert tentar(client, "senha-de-teste-123").status_code == 429


def test_trocar_de_ipv6_na_mesma_rede_nao_zera_o_contador(client, criar_usuario):
    criar_usuario("maria")
    for final in range(1, 5):
        resposta = client.post(
            reverse("login"),
            {"username": "maria", "password": "errada"},
            REMOTE_ADDR=f"2001:db8:1:{final}::{final}",
        )
        assert resposta.status_code == 200
    resposta = client.post(
        reverse("login"),
        {"username": "maria", "password": "errada"},
        REMOTE_ADDR="2001:db8:1:ffff::9",
    )
    assert resposta.status_code == 429
    # Another /48 network is not affected.
    resposta = client.post(
        reverse("login"),
        {"username": "maria", "password": "senha-de-teste-123"},
        REMOTE_ADDR="2001:db8:2::1",
    )
    assert resposta.status_code == 302


@pytest.mark.parametrize(
    ("endereco", "esperado"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:abcd:12:34::1", "2001:db8:abcd::"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("", None),
    ],
)
def test_ip_para_bloqueio(rf, endereco, esperado):
    from apps.core.seguranca import ip_para_bloqueio

    assert ip_para_bloqueio(rf.get("/", REMOTE_ADDR=endereco)) == esperado


def test_login_certo_zera_o_contador(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        tentar(client, "errada")
    assert tentar(client, "senha-de-teste-123").status_code == 302
    client.post(reverse("logout"))
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200


def test_usuario_novo_comeca_na_versao_atual_sem_aviso(client, criar_usuario):
    """Review (superuser, fresh install): a new person saw "the system was updated"."""
    usuario = criar_usuario("novata")
    assert usuario.ultima_versao_vista == releases.versao_atual()
    client.force_login(usuario)
    assert "Veja o que mudou" not in client.get(reverse("inicio")).content.decode()


def test_aviso_de_versao_nova_ate_abrir_as_novidades(client, criar_usuario):
    usuario = criar_usuario("maria")
    usuario.ultima_versao_vista = "0.40.0"  # seen before this version came out
    usuario.save(update_fields=["ultima_versao_vista"])
    client.force_login(usuario)
    assert "Veja o que mudou" in client.get(reverse("inicio")).content.decode()
    client.get(reverse("novidades"))
    usuario.refresh_from_db()
    assert usuario.ultima_versao_vista == releases.versao_atual()
    assert "Veja o que mudou" not in client.get(reverse("inicio")).content.decode()


def test_novidades_filtradas_por_modulo(client, criar_usuario):
    client.force_login(criar_usuario("maria"))
    resposta = client.get(reverse("novidades"), {"modulo": "Agenda"})
    modulos = {item.modulo for _, itens in resposta.context["versoes"] for item in itens}
    assert modulos == {"Agenda"}
    assert ("Pacientes", "Pacientes") in resposta.context["modulos"]


def test_ip_real_atras_do_proxy(rf):
    from apps.core.middleware import ProxyReversoMiddleware

    request = rf.get("/", HTTP_X_FORWARDED_FOR="2804:abcd::1, 2001:db8::7", REMOTE_ADDR="::1")
    ProxyReversoMiddleware(lambda r: None)(request)
    assert request.META["REMOTE_ADDR"] == "2001:db8::7"


# --- Content-Security-Policy (0.23.1) -------------------------------------------------

PASTA_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_paginas_saem_com_csp_sem_script_inline(client):
    politica = client.get(reverse("login"))["Content-Security-Policy"]
    assert "script-src 'self'" in politica
    assert "unsafe-inline" not in politica.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in politica


def test_templates_sem_script_inline_nem_eventos():
    """The CSP blocks inline scripts and onclick-style attributes: behaviour goes in static/js."""
    proibidos = re.compile(
        r"<script(?![^>]*\b(src=|type=\"application/json\"))|\son[a-z]+=|\bhx-on", re.I
    )
    problemas = [
        f"{arquivo.relative_to(PASTA_TEMPLATES)}: {achado.group(0)}"
        for arquivo in PASTA_TEMPLATES.rglob("*.html")
        for achado in proibidos.finditer(arquivo.read_text(encoding="utf-8"))
    ]
    assert problemas == []


def test_documentacao_da_api_so_para_superusuario(client, criar_usuario):
    docs = reverse("api-v1:openapi-view")
    assert client.get(docs).status_code == 302  # to the login page
    client.force_login(criar_usuario("maria"))
    assert client.get(docs).status_code == 302
    client.force_login(criar_usuario("dono", is_superuser=True, is_staff=True))
    resposta = client.get(docs)
    assert resposta.status_code == 200
    assert "cdn" not in resposta.content.decode().lower()  # local files, allowed by the CSP
    # The endpoints themselves stay open to the app.
    client.logout()
    assert client.get(reverse("api-v1:versao")).status_code == 200
