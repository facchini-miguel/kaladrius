"""The addresses before decision 155 (urls_before_decision_155.txt: every URL name and route of
0.55.0) answer with a permanent redirect to an English address that exists, with the same ids,
the values inside the address translated and the query string kept."""

import re
from pathlib import Path

import pytest
from django.urls import resolve

from config.legacy_urls import RedirecionamentoPermanente

pytestmark = pytest.mark.django_db

ANTES = Path(__file__).with_name("urls_before_decision_155.txt")
# A value for each converter of the old routes.
EXEMPLOS = {
    "<int:pk>": "7",
    "<int:paciente>": "3",
    "<int:item>": "2",
    "<str:tipo>": "retirada",
    "<uidb64>": "MQ",
    "<token>": "abc-123",
    "<slug:pagina>": "agenda",
    "<path:caminho>": "instalacao/requisitos",
}
REGEX = {
    "financeiro:cadastro": [
        f"financeiro/{c}/" for c in ("categorias", "contas", "centros-de-custo")
    ],
    "financeiro:cadastro_novo": ["financeiro/categorias/novo/"],
    "financeiro:cadastro_editar": ["financeiro/contas/7/"],
    "financeiro:transacao": [
        f"financeiro/transacoes/7/{a}/" for a in ("conciliar", "ignorar", "desfazer")
    ],
}


def enderecos_antigos():
    for linha in ANTES.read_text().splitlines():
        nome, _, rota = linha.partition("  ")
        if nome.startswith("api-v1:") or nome == "-:inicio" or not linha.strip():
            continue  # the API keeps its old addresses itself; "" is still the home page
        if nome in REGEX:
            yield from ((nome, f"/{caminho}") for caminho in REGEX[nome])
            continue
        for conversor, valor in EXEMPLOS.items():
            rota = rota.replace(conversor, valor)
        assert "<" not in rota, linha
        yield nome, f"/{rota}"


@pytest.mark.parametrize(("nome", "antigo"), list(enderecos_antigos()))
def test_endereco_antigo_redireciona_para_o_novo(client, nome, antigo):
    resposta = client.get(antigo)
    assert resposta.status_code == RedirecionamentoPermanente.status_code, (nome, antigo)
    destino = resolve(resposta.url)
    assert destino.func.__name__ != "redirecionar", (antigo, resposta.url)
    assert resposta.url != antigo
    # The ids go along; nothing Portuguese is left in the new address (the help pages' slugs
    # are page names, kept for the old in-system help).
    for chave in ("pk", "paciente", "item"):
        if chave in destino.kwargs:
            assert str(destino.kwargs[chave]) == EXEMPLOS[f"<int:{chave}>"]
    if not nome.startswith("ajuda:"):
        caminho = resposta.url.split("?")[0]
        assert not re.search(
            r"/(conta|pacientes|agenda|financeiro|novo|editar|excluir|retirada|contas|conciliar)/",
            caminho,
        ), caminho


def test_o_redirecionamento_mantem_a_query_string_e_o_metodo(client):
    resposta = client.get("/pacientes/?busca=Ana&pagina=2")
    assert resposta.url == "/patients/?busca=Ana&pagina=2"
    # 308: a form opened before the update and sent after it is sent again to the new address.
    resposta = client.post("/conta/login/", {"username": "x"})
    assert resposta.status_code == 308 and resposta.url == "/account/login/"
