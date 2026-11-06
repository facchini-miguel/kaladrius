"""Help menu: user manual for everyone, technical documentation for superusers only."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.core.models import Role
from apps.help import documents

pytestmark = pytest.mark.django_db


@pytest.fixture
def reception(clinic_a, create_user, client_for):
    return client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))


@pytest.fixture
def superuser(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("root", password="x-123456789"))
    return client


@pytest.mark.parametrize("folder", documents.FOLDERS.values())
def test_site_manual_and_policy_in_each_language(folder):
    manual = documents.DOCS / folder / "manual"
    pages = {file.stem for file in manual.glob("*.md")}
    assert {"getting-started", "schedule", "patients", "privacy"} <= pages, folder


def test_help_menu_opens_site_in_user_language(reception, settings, django_user_model):
    settings.DOCS_URL = "https://docs.exemplo.test/"
    page = reception.get(reverse("home")).content.decode()
    assert 'href="https://docs.exemplo.test/pt-BR/manual/getting-started"' in page
    assert 'href="https://docs.exemplo.test/pt-BR/"' in page
    user = django_user_model.objects.get(username="recepcao")
    user.language = "en"
    user.save()
    page = reception.get(reverse("home")).content.decode()
    assert 'href="https://docs.exemplo.test/manual/getting-started"' in page


def test_old_help_addresses_lead_to_the_site(reception, settings):
    settings.DOCS_URL = "https://docs.exemplo.test"
    site = "https://docs.exemplo.test/pt-BR/"
    assert reception.get(reverse("help:index")).url == site + "manual/getting-started"
    assert reception.get(reverse("help:manual", args=["agenda"])).url == site + "manual/schedule"
    assert reception.get(reverse("help:technical_index")).url == site
    assert reception.get(reverse("help:technical", args=["pt-BR/deploy.md"])).url == site
    assert reception.get(reverse("help:manual", args=["privacidade"])).url == reverse("privacy")


def test_list_right_after_a_paragraph_becomes_a_list():
    text = "Texto:\n- um\n- dois\n\n```\nlinha:\n- dentro do codigo\n```"
    result = documents._split_lists(text)
    assert result.startswith("Texto:\n\n- um\n- dois")
    assert "linha:\n- dentro do codigo" in result  # code blocks untouched


def test_github_release_notes_in_english():
    output = StringIO()
    call_command("release_notes", "0.7.0", "--title", stdout=output)
    assert output.getvalue().strip() == "0.7.0 – Audit log and security (end of phase 1)"
    output = StringIO()
    call_command("release_notes", "0.7.0", stdout=output)
    assert output.getvalue().startswith("- **New · Audit log:** The clinic administrator")
    with pytest.raises(CommandError):
        call_command("release_notes", "9.9.9")


def test_public_privacy_policy_with_clinic_contact(client, clinic_a):
    clinic_a.email = "privacidade@sorriso.com.br"
    clinic_a.save()
    login = client.get(reverse("login")).content.decode()
    assert reverse("privacy") in login
    response = client.get(reverse("privacy"))  # no login: patients do not log in
    page = response.content.decode()
    assert response.status_code == 200
    assert "Política de privacidade" in page and "20 anos" in page
    assert clinic_a.name in page and "privacidade@sorriso.com.br" in page


def test_policy_with_the_installation_clinic_contact(client, clinic_a, reception):
    assert reception.get(reverse("privacy")).context["clinic"] == clinic_a
    reception.logout()
    assert reception.get(reverse("privacy")).context["clinic"] == clinic_a


def test_policy_without_registered_clinic(client):
    page = client.get(reverse("privacy"))
    assert page.context["clinic"] is None
    assert "Fale com a clínica que atende você." in page.content.decode()


@pytest.mark.parametrize(
    ("language", "title"), [("en", "Privacy policy"), ("es", "Política de privacidad")]
)
def test_policy_in_the_three_languages(client, language, title):
    page = client.get(reverse("privacy"), HTTP_ACCEPT_LANGUAGE=language).content.decode()
    assert f"<h1>{title}</h1>" in page


def test_logo_in_bar_login_and_tab(client, reception):
    entry_line = client.get(reverse("login")).content.decode()
    assert "logo-login" in entry_line and "img/favicon" in entry_line
    assert "logo-bar" in reception.get(reverse("home")).content.decode()
    for file in ("logo.svg", "favicon.svg"):
        assert (documents.DOCS.parent / "static" / "img" / file).is_file()


def test_system_name_in_login_bar_and_tab(client, reception):
    entry_line = client.get(reverse("login")).content.decode()
    assert "<title>Entrar · Kaladrius</title>" in entry_line
    assert '<h1 class="h4 mb-4 text-center">Kaladrius</h1>' in entry_line
    start = reception.get(reverse("home")).content.decode()
    assert "Kaladrius · versão" in start
    for page in (entry_line, start):
        assert "Medical System" not in page
