"""Login brute-force protection (django-axes), the "new version" notice and the CSP."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.whats_new import releases

pytestmark = pytest.mark.django_db


def attempt(client, password):
    return client.post(reverse("login"), {"username": "maria", "password": password})


def test_blocks_after_5_wrong_passwords(client, create_user):
    create_user("maria")
    for _ in range(4):
        assert attempt(client, "errada").status_code == 200
    response = attempt(client, "errada")
    assert response.status_code == 429
    assert "bloqueado temporariamente" in response.content.decode()
    # Even the right password is refused while locked out.
    assert attempt(client, "senha-de-teste-123").status_code == 429


def test_changing_ipv6_in_same_network_does_not_reset_counter(client, create_user):
    create_user("maria")
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
    ("address", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:abcd:12:34::1", "2001:db8:abcd::"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("", None),
    ],
)
def test_ip_for_blocking(rf, address, expected):
    from apps.core.security import ip_for_lockout

    assert ip_for_lockout(rf.get("/", REMOTE_ADDR=address)) == expected


def test_right_login_resets_the_counter(client, create_user):
    create_user("maria")
    for _ in range(4):
        attempt(client, "errada")
    assert attempt(client, "senha-de-teste-123").status_code == 302
    client.post(reverse("logout"))
    for _ in range(4):
        assert attempt(client, "errada").status_code == 200


def test_new_user_starts_on_current_version_without_notice(client, create_user):
    """Review (superuser, fresh install): a new person saw "the system was updated"."""
    user = create_user("novata")
    assert user.last_seen_version == releases.current_version()
    client.force_login(user)
    assert "Veja o que mudou" not in client.get(reverse("home")).content.decode()


def test_new_version_notice_until_whats_new_is_opened(client, create_user):
    user = create_user("maria")
    user.last_seen_version = "0.40.0"  # seen before this version came out
    user.save(update_fields=["last_seen_version"])
    client.force_login(user)
    assert "Veja o que mudou" in client.get(reverse("home")).content.decode()
    client.get(reverse("whats_new"))
    user.refresh_from_db()
    assert user.last_seen_version == releases.current_version()
    assert "Veja o que mudou" not in client.get(reverse("home")).content.decode()


def test_whats_new_filtered_by_module(client, create_user):
    client.force_login(create_user("maria"))
    response = client.get(reverse("whats_new"), {"module": "Agenda"})
    modules = {item.module for _, items in response.context["versions"] for item in items}
    assert modules == {"Agenda"}
    assert ("Pacientes", "Pacientes") in response.context["modules"]


def test_real_ip_behind_the_proxy(rf):
    from apps.core.middleware import ReverseProxyMiddleware

    request = rf.get("/", HTTP_X_FORWARDED_FOR="2804:abcd::1, 2001:db8::7", REMOTE_ADDR="::1")
    ReverseProxyMiddleware(lambda r: None)(request)
    assert request.META["REMOTE_ADDR"] == "2001:db8::7"


# --- Content-Security-Policy (0.23.1) -------------------------------------------------

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_pages_ship_csp_without_inline_script(client):
    policy = client.get(reverse("login"))["Content-Security-Policy"]
    assert "script-src 'self'" in policy
    assert "unsafe-inline" not in policy.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in policy


def test_templates_without_inline_script_or_events():
    """The CSP blocks inline scripts and onclick-style attributes: behaviour goes in static/js."""
    forbidden = re.compile(
        r"<script(?![^>]*\b(src=|type=\"application/json\"))|\son[a-z]+=|\bhx-on", re.I
    )
    problems = [
        f"{file.relative_to(TEMPLATES_DIR)}: {found.group(0)}"
        for file in TEMPLATES_DIR.rglob("*.html")
        for found in forbidden.finditer(file.read_text(encoding="utf-8"))
    ]
    assert problems == []


def test_api_docs_only_for_superuser(client, create_user):
    docs = reverse("api-v1:openapi-view")
    assert client.get(docs).status_code == 302  # to the login page
    client.force_login(create_user("maria"))
    assert client.get(docs).status_code == 302
    client.force_login(create_user("dono", is_superuser=True, is_staff=True))
    response = client.get(docs)
    assert response.status_code == 200
    assert "cdn" not in response.content.decode().lower()  # local files, allowed by the CSP
    # The endpoints themselves stay open to the app.
    client.logout()
    assert client.get(reverse("api-v1:versao")).status_code == 200
