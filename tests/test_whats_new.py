import textwrap

import pytest
from django.conf import settings
from django.urls import reverse

from apps.whats_new import releases


@pytest.fixture
def arquivo(tmp_path):
    def criar(conteudo):
        path = tmp_path / "releases.yaml"
        path.write_text(textwrap.dedent(conteudo), encoding="utf-8")
        return path

    return criar


EXEMPLO = """
- versao: 1.5.0
  data: 2027-03-10
  titulo: Lembretes
  itens:
    - tipo: novo
      modulo: Rechamadas
      publico: [equipe, paciente]
      texto: Aviso no celular.
    - tipo: melhoria
      modulo: Agenda
      publico: [equipe]
      texto: Agenda mais rápida.
- versao: 1.4.7
  data: 2027-02-01
  itens:
    - tipo: correcao
      modulo: Agenda
      publico: [equipe]
      texto: Corrigido horário de verão.
"""


def test_project_file_is_valid():
    """Ensures the repository's releases.yaml is always valid (runs in CI)."""
    versions = releases.read_releases(settings.RELEASES_FILE)
    assert versions


@pytest.mark.parametrize(
    ("arquivo", "texto"),
    [
        ("README.md", "Current version: {}"),
        ("README.pt-BR.md", "Versão atual: {}"),
        ("README.es.md", "Versión actual: {}"),
    ],
)
def test_readme_shows_current_version(arquivo, texto):
    readme = (settings.BASE_DIR / arquivo).read_text(encoding="utf-8")
    assert texto.format(releases.current_version()) in readme, f"update the version in {arquivo}"


def test_pyproject_version_equals_releases():
    import tomllib

    pyproject = tomllib.loads((settings.BASE_DIR / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == releases.current_version()


def test_reading_and_filtering_by_audience(arquivo, settings):
    settings.RELEASES_FILE = arquivo(EXEMPLO)
    releases.all_releases.cache_clear()
    try:
        assert releases.current_version() == "1.5.0"
        patient = releases.for_audience("paciente")
        assert [r.versao for r, _ in patient] == ["1.5.0"]
        assert [i.modulo for i in patient[0][1]] == ["Rechamadas"]
        equipe_desde = releases.for_audience("equipe", desde="1.4.7")
        assert [r.versao for r, _ in equipe_desde] == ["1.5.0"]
    finally:
        releases.all_releases.cache_clear()


@pytest.mark.parametrize(
    ("conteudo", "message"),
    [
        ("- versao: 1.0\n  data: 2027-01-01\n  itens: []", "formato"),
        (
            "- versao: 1.0.0\n  data: 2027-01-01\n  itens:\n"
            "    - {tipo: x, modulo: A, publico: [equipe], texto: t}",
            "tipo",
        ),
        (
            "- versao: 1.0.0\n  data: 2027-01-01\n  itens:\n"
            "    - {tipo: novo, modulo: A, publico: [todos], texto: t}",
            "publico",
        ),
        (
            "- versao: 1.0.0\n  data: 2027-01-01\n  itens:\n"
            "    - {tipo: novo, modulo: A, publico: [equipe], texto: t, origem: robo, pr: 1}",
            "origem",
        ),
        (
            "- versao: 1.0.0\n  data: 2027-01-01\n  itens:\n"
            "    - {tipo: novo, modulo: A, publico: [equipe], texto: t, origem: dependabot}",
            "pr",
        ),
        (
            "- versao: 1.0.0\n  data: 2027-01-01\n  itens:\n"
            "    - {tipo: novo, modulo: A, publico: [equipe], texto: t}\n"
            "- versao: 1.1.0\n  data: 2027-01-02\n  itens:\n"
            "    - {tipo: novo, modulo: A, publico: [equipe], texto: t}",
            "Ordem",
        ),
    ],
)
def test_invalid_file(arquivo, conteudo, message):
    with pytest.raises(releases.InvalidReleases, match=message):
        releases.read_releases(arquivo(conteudo))


@pytest.mark.django_db
def test_whats_new_page(client, django_user_model):
    user = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(user)
    conteudo = client.get(reverse("whats_new")).content.decode()
    assert f"Versão {releases.current_version()}" in conteudo
    # Items with an empty publico are hidden from everyone
    assert "Estrutura do projeto, Docker" not in conteudo


@pytest.mark.django_db
def test_whats_new_page_requires_login(client):
    assert client.get(reverse("whats_new")).status_code == 302


@pytest.mark.django_db
def test_api_releases(client):
    response = client.get("/api/v1/releases?publico=paciente")
    assert response.status_code == 200
    data = response.json()
    # Only versions with patient-facing items are returned, newest first.
    esperadas = [release.versao for release, _ in releases.for_audience("paciente")]
    assert [versao["versao"] for versao in data] == esperadas
    modulos = {item["modulo"] for versao in data for item in versao["itens"]}
    assert "Acesso" not in modulos  # staff-only items never reach patients


@pytest.mark.django_db
def test_api_version(client):
    assert client.get("/api/v1/version").json() == {"version": releases.current_version()}
    assert client.get("/api/v1/versao").json() == {"versao": releases.current_version()}


DEPENDABOT = """
- versao: 2.0.0
  data: 2027-05-01
  itens:
    - tipo: seguranca
      modulo: Sistema
      publico: [equipe, paciente]
      origem: dependabot
      pr: 42
      texto: Biblioteca atualizada.
    - tipo: novo
      modulo: Agenda
      publico: [equipe, paciente]
      texto: Feito pelo projeto.
"""


@pytest.mark.django_db
def test_dependabot_items_show_marked(arquivo, settings, client, django_user_model):
    """Decision 133: Dependabot's items say so, with their pull request; the project's do not."""
    from io import StringIO

    from django.core.management import call_command

    settings.RELEASES_FILE = arquivo(DEPENDABOT)
    releases.all_releases.cache_clear()
    try:
        user = django_user_model.objects.create_user(username="bia", password="x-1234567890")
        client.force_login(user)
        page = client.get(reverse("whats_new")).content.decode()
        assert 'href="https://github.com/facchini-miguel/kaladrius/pull/42"' in page
        assert 'target="_blank" rel="noopener noreferrer"' in page  # opens in a new tab
        assert "Dependabot · #42" in page and page.count("Dependabot ·") == 1
        data = client.get("/api/v1/releases?publico=paciente").json()
        assert [(i["origem"], i["pr"]) for i in data[0]["itens"]] == [
            ("Dependabot", 42),
            (None, None),
        ]
        saida = StringIO()
        call_command("release_notes", "2.0.0", stdout=saida)
        rows = saida.getvalue().splitlines()
        assert rows[0].endswith("Biblioteca atualizada. (Dependabot, #42)")
        assert rows[1].endswith("Feito pelo projeto.")
    finally:
        releases.all_releases.cache_clear()
