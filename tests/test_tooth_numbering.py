"""Tooth numbering (decision 122): teeth are stored in FDI and shown in the clinic's numbering,
FDI, Universal (United States, the default there) or Palmer."""

import pytest
from django.urls import reverse

from apps.core.forms import NovaClinicaForm
from apps.core.isolamento import usar_clinica
from apps.odontologia.dentes import (
    DENTES_DECIDUOS,
    DENTES_PERMANENTES,
    FDI,
    PALMER,
    UNIVERSAL,
    nome,
    ordenar,
)
from tests.test_core import dados_clinica
from tests.test_estimates import cenario, criar_orcamento, entrar, incluir  # noqa: F401

pytestmark = pytest.mark.django_db

PERMANENTES = [d for linha in DENTES_PERMANENTES for d in linha]
DECIDUOS = [d for linha in DENTES_DECIDUOS for d in linha]


@pytest.mark.parametrize(
    ("fdi", "universal", "palmer"),
    [
        (18, "1", "UR8"),
        (11, "8", "UR1"),
        (21, "9", "UL1"),
        (28, "16", "UL8"),
        (38, "17", "LL8"),
        (36, "19", "LL6"),
        (31, "24", "LL1"),
        (41, "25", "LR1"),
        (48, "32", "LR8"),
        (55, "A", "URE"),
        (65, "J", "ULE"),
        (75, "K", "LLE"),
        (85, "T", "LRE"),
    ],
)
def test_nomes_de_cada_numeracao(fdi, universal, palmer):
    nomes = (nome(fdi, FDI), nome(fdi, UNIVERSAL), nome(fdi, PALMER))
    assert nomes == (str(fdi), universal, palmer)


def test_cada_dente_tem_um_nome_so():
    for numeracao in (FDI, UNIVERSAL, PALMER):
        nomes = [nome(d, numeracao) for d in PERMANENTES + DECIDUOS]
        assert len(set(nomes)) == 52, numeracao
    assert sorted(int(nome(d, UNIVERSAL)) for d in PERMANENTES) == list(range(1, 33))
    assert sorted(nome(d, UNIVERSAL) for d in DECIDUOS) == list("ABCDEFGHIJKLMNOPQRST")


def test_ordem_da_numeracao():
    assert [nome(d, UNIVERSAL) for d in ordenar([85, 36, 11, 55, 18], UNIVERSAL)] == [
        "1",
        "8",
        "19",
        "A",
        "T",
    ]
    assert ordenar([36, 11], PALMER) == [11, 36]


def test_numeracao_acompanha_o_pais(clinica_a, criar_usuario, cliente_de):
    from apps.core.models import Papel

    admin = cliente_de(criar_usuario("admin_numeracao", clinica_a, Papel.ADMIN))
    assert clinica_a.numeracao_dentaria == FDI
    assert admin.post(reverse("configuracoes"), dados_clinica(pais="US")).status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.numeracao_dentaria == UNIVERSAL
    # Chosen on purpose, it stays when the country changes.
    dados = dados_clinica(pais="US", numeracao_dentaria=PALMER)
    assert admin.post(reverse("configuracoes"), dados).status_code == 302
    dados = dados_clinica(pais="GB", numeracao_dentaria=PALMER)
    assert admin.post(reverse("configuracoes"), dados).status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.numeracao_dentaria == PALMER


def test_clinica_nova_nos_estados_unidos_comeca_com_a_universal():
    form = NovaClinicaForm({"nome": "Smile Fictitious", "area": "odontologia", "pais": "US"})
    assert form.is_valid(), form.errors
    assert form.instance.numeracao_dentaria == UNIVERSAL


def test_orcamento_mostra_a_numeracao_da_clinica(cenario):  # noqa: F811
    clinica = cenario["clinica"]
    clinica.numeracao_dentaria = UNIVERSAL
    clinica.save()
    cliente = entrar(cenario, "profissional")
    orcamento = criar_orcamento(cenario, cliente)
    incluir(cliente, orcamento, procedimento=cenario["restauracao"].pk, dentes="36,18")
    with usar_clinica(clinica):
        item = orcamento.itens.get()
        assert item.dentes == "18,36"  # always FDI in the database
        assert item.dentes_exibicao == "1, 19"
    pagina = cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).content.decode()
    # The chart posts FDI and shows the Universal number.
    assert 'data-dente="36"' in pagina and ">19</button>" in pagina
    assert "Numeração universal (Estados Unidos)." in pagina
