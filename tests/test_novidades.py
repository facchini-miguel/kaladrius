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
    assert dados[0]["versao"] == releases.versao_atual()
    assert all(item["modulo"] != "Acesso" for item in dados[0]["itens"])  # staff-only item


@pytest.mark.django_db
def test_api_versao(client):
    assert client.get("/api/v1/versao").json() == {"versao": releases.versao_atual()}
