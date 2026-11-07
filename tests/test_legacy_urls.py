"""The addresses before decision 155 (urls_before_decision_155.txt: every URL name and route of
0.55.0) answer with a permanent redirect to an English address that exists, with the same ids,
the values inside the address translated and the query string kept."""

import re
from pathlib import Path

import pytest
from django.urls import resolve

from config.legacy_urls import PermanentRedirect

pytestmark = pytest.mark.django_db

BEFORE = Path(__file__).with_name("urls_before_decision_155.txt")
# A value for each converter of the old routes.
EXAMPLES = {
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


def old_addresses():
    for row in BEFORE.read_text().splitlines():
        name, _, route = row.partition("  ")
        if name.startswith("api-v1:") or name == "-:inicio" or not row.strip():
            continue  # the API keeps its old addresses itself; "" is still the home page
        if name in REGEX:
            yield from ((name, f"/{path}") for path in REGEX[name])
            continue
        for converter, value in EXAMPLES.items():
            route = route.replace(converter, value)
        assert "<" not in route, row
        yield name, f"/{route}"


@pytest.mark.parametrize(("name", "old"), list(old_addresses()))
def test_old_address_redirects_to_the_new(client, name, old):
    response = client.get(old)
    assert response.status_code == PermanentRedirect.status_code, (name, old)
    destination = resolve(response.url)
    assert destination.func.__name__ != "redirecionar", (old, response.url)
    assert response.url != old
    # The ids go along; nothing Portuguese is left in the new address (the help pages' slugs
    # are page names, kept for the old in-system help).
    # The argument names changed too (decision 161: `paciente` is now `patient`).
    for key, old_one in (("pk", "pk"), ("patient", "paciente"), ("item", "item")):
        if key in destination.kwargs:
            assert str(destination.kwargs[key]) == EXAMPLES[f"<int:{old_one}>"]
    if not name.startswith("ajuda:"):
        path = response.url.split("?")[0]
        assert not re.search(
            r"/(conta|pacientes|agenda|financeiro|novo|editar|excluir|retirada|contas|conciliar)/",
            path,
        ), path


def test_redirect_keeps_query_string_and_method(client):
    response = client.get("/pacientes/?q=Ana&pagina=2")
    assert response.url == "/patients/?q=Ana&page=2"
    # The old filter names are translated (decision 184).
    response = client.get("/financeiro/fluxo-de-caixa/?de=2031-03-01&ate=2031-03-31&agrupar=mes")
    assert response.url == "/finance/cash-flow/?since=2031-03-01&until=2031-03-31&group=month"
    # 308: a form opened before the update and sent after it is sent again to the new address.
    response = client.post("/conta/login/", {"username": "x"})
    assert response.status_code == 308 and response.url == "/account/login/"
