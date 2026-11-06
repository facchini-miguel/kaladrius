"""Login brute-force protection (django-axes), the "new version" notice and the CSP."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.whats_new import releases

pytestmark = pytest.mark.django_db


def tentar(client, password):
    return client.post(reverse("login"), {"username": "maria", "password": password})


def test_blocks_after_5_wrong_passwords(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200
    response = tentar(client, "errada")
    assert response.status_code == 429
    assert "bloqueado temporariamente" in response.content.decode()
    # Even the right password is refused while locked out.
    assert tentar(client, "senha-de-teste-123").status_code == 429


def test_changing_ipv6_in_same_network_does_not_reset_counter(client, criar_usuario):
    criar_usuario("maria")
    for final in range(1, 5):
        response = client.post(
            reverse("login"),
            {"username": "maria", "password": "errada"},
            REMOTE_ADDR=f"2001:db8:1:{final}::{final}",
        )
        assert response.status_code == 200
    response = client.post(
        reverse("login"),
        {"username": "maria", "password": "errada"},
        REMOTE_ADDR="2001:db8:1:ffff::9",
    )
    assert response.status_code == 429
    # Another /48 network is not affected.
    response = client.post(
        reverse("login"),
        {"username": "maria", "password": "senha-de-teste-123"},
        REMOTE_ADDR="2001:db8:2::1",
    )
    assert response.status_code == 302


@pytest.mark.parametrize(
    ("address", "esperado"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:abcd:12:34::1", "2001:db8:abcd::"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("", None),
    ],
)
def test_ip_for_blocking(rf, address, esperado):
    from apps.core.security import ip_for_lockout

    assert ip_for_lockout(rf.get("/", REMOTE_ADDR=address)) == esperado


def test_right_login_resets_the_counter(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        tentar(client, "errada")
    assert tentar(client, "senha-de-teste-123").status_code == 302
    client.post(reverse("logout"))
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200


def test_new_user_starts_on_current_version_without_notice(client, criar_usuario):
    """Review (superuser, fresh install): a new person saw "the system was updated"."""
    user = criar_usuario("novata")
    assert user.last_seen_version == releases.current_version()
    client.force_login(user)
    assert "Veja o que mudou" not in client.get(reverse("home")).content.decode()


def test_new_version_notice_until_whats_new_is_opened(client, criar_usuario):
    user = criar_usuario("maria")
    user.last_seen_version = "0.40.0"  # seen before this version came out
    user.save(update_fields=["last_seen_version"])
    client.force_login(user)
    assert "Veja o que mudou" in client.get(reverse("home")).content.decode()
    client.get(reverse("whats_new"))
    user.refresh_from_db()
    assert user.last_seen_version == releases.current_version()
    assert "Veja o que mudou" not in client.get(reverse("home")).content.decode()


def test_whats_new_filtered_by_module(client, criar_usuario):
    client.force_login(criar_usuario("maria"))
    response = client.get(reverse("whats_new"), {"module": "Agenda"})
    modulos = {item.modulo for _, itens in response.context["versions"] for item in itens}
    assert modulos == {"Agenda"}
    assert ("Pacientes", "Pacientes") in response.context["modules"]


def test_real_ip_behind_the_proxy(rf):
    from apps.core.middleware import ReverseProxyMiddleware

    request = rf.get("/", HTTP_X_FORWARDED_FOR="2804:abcd::1, 2001:db8::7", REMOTE_ADDR="::1")
    ReverseProxyMiddleware(lambda r: None)(request)
    assert request.META["REMOTE_ADDR"] == "2001:db8::7"


# --- Content-Security-Policy (0.23.1) -------------------------------------------------

PASTA_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_pages_ship_csp_without_inline_script(client):
    politica = client.get(reverse("login"))["Content-Security-Policy"]
    assert "script-src 'self'" in politica
    assert "unsafe-inline" not in politica.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in politica


def test_templates_without_inline_script_or_events():
    """The CSP blocks inline scripts and onclick-style attributes: behaviour goes in static/js."""
    proibidos = re.compile(
        r"<script(?![^>]*\b(src=|type=\"application/json\"))|\son[a-z]+=|\bhx-on", re.I
    )
    problemas = [
        f"{file.relative_to(PASTA_TEMPLATES)}: {achado.group(0)}"
        for file in PASTA_TEMPLATES.rglob("*.html")
        for achado in proibidos.finditer(file.read_text(encoding="utf-8"))
    ]
    assert problemas == []


def test_api_docs_only_for_superuser(client, criar_usuario):
    docs = reverse("api-v1:openapi-view")
    assert client.get(docs).status_code == 302  # to the login page
    client.force_login(criar_usuario("maria"))
    assert client.get(docs).status_code == 302
    client.force_login(criar_usuario("dono", is_superuser=True, is_staff=True))
    response = client.get(docs)
    assert response.status_code == 200
    assert "cdn" not in response.content.decode().lower()  # local files, allowed by the CSP
    # The endpoints themselves stay open to the app.
    client.logout()
    assert client.get(reverse("api-v1:versao")).status_code == 200
