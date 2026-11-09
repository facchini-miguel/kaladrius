import textwrap

import pytest
from django.conf import settings
from django.urls import reverse

from apps.whats_new import releases


@pytest.fixture
def file_path(tmp_path):
    def create(page_content):
        path = tmp_path / "releases.yaml"
        path.write_text(textwrap.dedent(page_content), encoding="utf-8")
        return path

    return create


EXAMPLE = """
- version: 1.5.0
  date: 2027-03-10
  title: Lembretes
  items:
    - kind: new
      module: Rechamadas
      audience: [staff, patient]
      text: Aviso no celular.
    - kind: improvement
      module: Agenda
      audience: [staff]
      text: Agenda mais rápida.
- version: 1.4.7
  date: 2027-02-01
  items:
    - kind: fix
      module: Agenda
      audience: [staff]
      text: Corrigido horário de verão.
"""


def test_project_file_is_valid():
    """Ensures the repository's releases.yaml is always valid (runs in CI)."""
    versions = releases.read_releases(settings.RELEASES_FILE)
    assert versions


@pytest.mark.parametrize(
    ("file_path", "text_"),
    [
        ("README.md", "Current version: {}"),
        ("README.pt-BR.md", "Versão atual: {}"),
        ("README.es.md", "Versión actual: {}"),
    ],
)
def test_readme_shows_current_version(file_path, text_):
    readme = (settings.BASE_DIR / file_path).read_text(encoding="utf-8")
    assert text_.format(releases.current_version()) in readme, f"update the version in {file_path}"


def test_pyproject_version_equals_releases():
    import tomllib

    pyproject = tomllib.loads((settings.BASE_DIR / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == releases.current_version()


def test_reading_and_filtering_by_audience(file_path, settings):
    settings.RELEASES_FILE = file_path(EXAMPLE)
    releases.all_releases.cache_clear()
    try:
        assert releases.current_version() == "1.5.0"
        patient = releases.for_audience("patient")
        assert [r.version for r, _ in patient] == ["1.5.0"]
        assert [i.module for i in patient[0][1]] == ["Rechamadas"]
        staff_since = releases.for_audience("staff", since="1.4.7")
        assert [r.version for r, _ in staff_since] == ["1.5.0"]
    finally:
        releases.all_releases.cache_clear()


@pytest.mark.parametrize(
    ("page_content", "message"),
    [
        ("- version: 1.0\n  date: 2027-01-01\n  items: []", "format"),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {kind: x, module: A, audience: [staff], text: t}",
            "kind",
        ),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {kind: new, module: A, audience: [todos], text: t}",
            "audience",
        ),
        # The format before decision 189 is refused, naming the field.
        ("- versao: 1.0.0\n  date: 2027-01-01\n  items: []", "unknown.*versao"),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {tipo: new, module: A, audience: [staff], text: t}",
            "unknown.*tipo",
        ),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {kind: new, module: A, audience: [staff], text: t, source: robo, pr: 1}",
            "source",
        ),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {kind: new, module: A, audience: [staff], text: t, source: dependabot}",
            "pr",
        ),
        (
            "- version: 1.0.0\n  date: 2027-01-01\n  items:\n"
            "    - {kind: new, module: A, audience: [staff], text: t}\n"
            "- version: 1.1.0\n  date: 2027-01-02\n  items:\n"
            "    - {kind: new, module: A, audience: [staff], text: t}",
            "Wrong order",
        ),
    ],
)
def test_invalid_file(file_path, page_content, message):
    with pytest.raises(releases.InvalidReleases, match=message):
        releases.read_releases(file_path(page_content))


@pytest.mark.django_db
def test_whats_new_page(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    page_content = client.get(reverse("whats_new")).content.decode()
    assert f"Versão {releases.current_version()}" in page_content
    # Items with an empty audience are hidden from everyone
    assert "Estrutura do projeto, Docker" not in page_content


@pytest.mark.django_db
def test_whats_new_page_requires_login(client):
    assert client.get(reverse("whats_new")).status_code == 302


@pytest.mark.django_db
def test_api_releases(client):
    response = client.get("/api/v1/releases?audience=patient")
    assert response.status_code == 200
    data = response.json()
    # Only versions with patient-facing items are returned, newest first.
    expected_ones = [release.version for release, _ in releases.for_audience("patient")]
    assert [version["version"] for version in data] == expected_ones
    assert set(data[0]) == {"version", "date", "title", "items"}
    assert set(data[0]["items"][0]) == {"kind", "kind_name", "module", "text", "source", "pr"}
    modules = {item["module"] for version in data for item in version["items"]}
    assert "Acesso" not in modules  # staff-only items never reach patients
    assert client.get("/api/v1/releases").json() == data  # patients are the default


@pytest.mark.django_db
def test_api_releases_filters(client):
    since = releases.all_releases()[3].version
    staff = client.get(f"/api/v1/releases?audience=staff&since={since}").json()
    assert 0 < len(staff) <= 3
    assert client.get("/api/v1/releases?audience=todos").status_code == 422


@pytest.mark.django_db
def test_api_version(client):
    assert client.get("/api/v1/version").json() == {"version": releases.current_version()}


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/v1/versao", "/api/v1/saude"])
def test_api_addresses_before_decision_155_are_gone(client, path):
    """Decision 196: nothing used them any more."""
    assert client.get(path).status_code == 404


DEPENDABOT = """
- version: 2.0.0
  date: 2027-05-01
  items:
    - kind: security
      module: Sistema
      audience: [staff, patient]
      source: dependabot
      pr: 42
      text: Biblioteca atualizada.
    - kind: new
      module: Agenda
      audience: [staff, patient]
      text: Feito pelo projeto.
"""


@pytest.mark.django_db
def test_dependabot_items_show_marked(file_path, settings, client, django_user_model):
    """Decision 133: Dependabot's items say so, with their pull request; the project's do not."""
    from io import StringIO

    from django.core.management import call_command

    settings.RELEASES_FILE = file_path(DEPENDABOT)
    releases.all_releases.cache_clear()
    try:
        user = django_user_model.objects.create_user(username="bia", password="x-1234567890")
        client.force_login(user)
        page = client.get(reverse("whats_new")).content.decode()
        assert 'href="https://github.com/facchini-miguel/kaladrius/pull/42"' in page
        assert 'target="_blank" rel="noopener noreferrer"' in page  # opens in a new tab
        assert "Dependabot · #42" in page and page.count("Dependabot ·") == 1
        data = client.get("/api/v1/releases?audience=patient").json()
        assert [(i["source"], i["pr"]) for i in data[0]["items"]] == [
            ("Dependabot", 42),
            (None, None),
        ]
        output = StringIO()
        call_command("release_notes", "2.0.0", stdout=output)
        rows = output.getvalue().splitlines()
        assert rows[0].endswith("Biblioteca atualizada. (Dependabot, #42)")
        assert rows[1].endswith("Feito pelo projeto.")
    finally:
        releases.all_releases.cache_clear()
