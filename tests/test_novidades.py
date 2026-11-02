import textwrap

import pytest
from django.conf import settings
from django.urls import reverse

from apps.novidades import releases


@pytest.fixture
def arquivo(tmp_path):
    def criar(conteudo):
        caminho = tmp_path / "releases.yaml"
        caminho.write_text(textwrap.dedent(conteudo), encoding="utf-8")
        return caminho

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


def test_arquivo_do_projeto_e_valido():
    """Ensures the repository's releases.yaml is always valid (runs in CI)."""
    versoes = releases.ler_releases(settings.RELEASES_ARQUIVO)
    assert versoes


@pytest.mark.parametrize(
    ("arquivo", "texto"),
    [
        ("README.md", "Current version: {}"),
        ("README.pt-BR.md", "Versão atual: {}"),
        ("README.es.md", "Versión actual: {}"),
    ],
)
def test_readme_mostra_a_versao_atual(arquivo, texto):
    readme = (settings.BASE_DIR / arquivo).read_text(encoding="utf-8")
    assert texto.format(releases.versao_atual()) in readme, f"update the version in {arquivo}"


def test_versao_do_pyproject_igual_a_do_releases():
    import tomllib

    pyproject = tomllib.loads((settings.BASE_DIR / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == releases.versao_atual()


def test_leitura_e_filtro_por_publico(arquivo, settings):
    settings.RELEASES_ARQUIVO = arquivo(EXEMPLO)
    releases.todas.cache_clear()
    try:
        assert releases.versao_atual() == "1.5.0"
        paciente = releases.para_publico("paciente")
        assert [r.versao for r, _ in paciente] == ["1.5.0"]
        assert [i.modulo for i in paciente[0][1]] == ["Rechamadas"]
        equipe_desde = releases.para_publico("equipe", desde="1.4.7")
        assert [r.versao for r, _ in equipe_desde] == ["1.5.0"]
    finally:
        releases.todas.cache_clear()


@pytest.mark.parametrize(
    ("conteudo", "mensagem"),
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
def test_arquivo_invalido(arquivo, conteudo, mensagem):
    with pytest.raises(releases.ReleasesInvalidas, match=mensagem):
        releases.ler_releases(arquivo(conteudo))


@pytest.mark.django_db
def test_pagina_novidades(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="ana", password="senha-de-teste-123")
    client.force_login(usuario)
    conteudo = client.get(reverse("novidades")).content.decode()
    assert f"Versão {releases.versao_atual()}" in conteudo
    # Items with an empty publico are hidden from everyone
    assert "Estrutura do projeto, Docker" not in conteudo


@pytest.mark.django_db
def test_pagina_novidades_exige_login(client):
    assert client.get(reverse("novidades")).status_code == 302


@pytest.mark.django_db
def test_api_releases(client):
    resposta = client.get("/api/v1/releases?publico=paciente")
    assert resposta.status_code == 200
    dados = resposta.json()
    # Only versions with patient-facing items are returned, newest first.
    esperadas = [release.versao for release, _ in releases.para_publico("paciente")]
    assert [versao["versao"] for versao in dados] == esperadas
    modulos = {item["modulo"] for versao in dados for item in versao["itens"]}
    assert "Acesso" not in modulos  # staff-only items never reach patients


@pytest.mark.django_db
def test_api_versao(client):
    assert client.get("/api/v1/versao").json() == {"versao": releases.versao_atual()}


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
def test_itens_do_dependabot_aparecem_marcados(arquivo, settings, client, django_user_model):
    """Decision 133: Dependabot's items say so, with their pull request; the project's do not."""
    from io import StringIO

    from django.core.management import call_command

    settings.RELEASES_ARQUIVO = arquivo(DEPENDABOT)
    releases.todas.cache_clear()
    try:
        usuario = django_user_model.objects.create_user(username="bia", password="x-1234567890")
        client.force_login(usuario)
        pagina = client.get(reverse("novidades")).content.decode()
        assert 'href="https://github.com/facchini-miguel/kaladrius/pull/42"' in pagina
        assert 'target="_blank" rel="noopener noreferrer"' in pagina  # opens in a new tab
        assert "Dependabot · #42" in pagina and pagina.count("Dependabot ·") == 1
        dados = client.get("/api/v1/releases?publico=paciente").json()
        assert [(i["origem"], i["pr"]) for i in dados[0]["itens"]] == [
            ("Dependabot", 42),
            (None, None),
        ]
        saida = StringIO()
        call_command("notas_release", "2.0.0", stdout=saida)
        linhas = saida.getvalue().splitlines()
        assert linhas[0].endswith("Biblioteca atualizada. (Dependabot, #42)")
        assert linhas[1].endswith("Feito pelo projeto.")
    finally:
        releases.todas.cache_clear()
