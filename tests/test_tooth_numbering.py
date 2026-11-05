"""Tooth numbering (decision 122): teeth are stored in FDI and shown in the clinic's numbering,
FDI, Universal (United States, the default there) or Palmer."""

import pytest
from django.urls import reverse

from apps.core.forms import NewClinicForm
from apps.core.isolation import use_clinic
from apps.dentistry.teeth import (
    FDI,
    PALMER,
    PERMANENT_TEETH,
    PRIMARY_TEETH,
    UNIVERSAL,
    name,
    sort_teeth,
)
from tests.test_core import dados_clinica
from tests.test_estimates import cenario, criar_orcamento, entrar, incluir  # noqa: F401

pytestmark = pytest.mark.django_db

PERMANENTES = [d for row in PERMANENT_TEETH for d in row]
DECIDUOS = [d for row in PRIMARY_TEETH for d in row]


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
    nomes = (name(fdi, FDI), name(fdi, UNIVERSAL), name(fdi, PALMER))
    assert nomes == (str(fdi), universal, palmer)


def test_cada_dente_tem_um_nome_so():
    for numeracao in (FDI, UNIVERSAL, PALMER):
        nomes = [name(d, numeracao) for d in PERMANENTES + DECIDUOS]
        assert len(set(nomes)) == 52, numeracao
    assert sorted(int(name(d, UNIVERSAL)) for d in PERMANENTES) == list(range(1, 33))
    assert sorted(name(d, UNIVERSAL) for d in DECIDUOS) == list("ABCDEFGHIJKLMNOPQRST")


def test_ordem_da_numeracao():
    assert [name(d, UNIVERSAL) for d in sort_teeth([85, 36, 11, 55, 18], UNIVERSAL)] == [
        "1",
        "8",
        "19",
        "A",
        "T",
    ]
    assert sort_teeth([36, 11], PALMER) == [11, 36]


def test_numeracao_acompanha_o_pais(clinica_a, criar_usuario, cliente_de):
    from apps.core.models import Role

    admin = cliente_de(criar_usuario("admin_numeracao", clinica_a, Role.ADMIN))
    assert clinica_a.tooth_numbering == FDI
    assert admin.post(reverse("clinic_settings"), dados_clinica(country="US")).status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.tooth_numbering == UNIVERSAL
    # Chosen on purpose, it stays when the country changes.
    data = dados_clinica(country="US", tooth_numbering=PALMER)
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    data = dados_clinica(country="GB", tooth_numbering=PALMER)
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.tooth_numbering == PALMER


def test_clinica_nova_nos_estados_unidos_comeca_com_a_universal():
    form = NewClinicForm({"name": "Smile Fictitious", "area": "odontologia", "country": "US"})
    assert form.is_valid(), form.errors
    assert form.instance.tooth_numbering == UNIVERSAL


def test_orcamento_mostra_a_numeracao_da_clinica(cenario):  # noqa: F811
    clinic = cenario["clinic"]
    clinic.tooth_numbering = UNIVERSAL
    clinic.save()
    cliente = entrar(cenario, "practitioner")
    estimate = criar_orcamento(cenario, cliente)
    incluir(cliente, estimate, procedure=cenario["restauracao"].pk, teeth="36,18")
    with use_clinic(clinic):
        item = estimate.itens.get()
        assert item.teeth == "18,36"  # always FDI in the database
        assert item.teeth_display == "1, 19"
    page = cliente.get(reverse("estimates:detail", args=[estimate.pk])).content.decode()
    # The chart posts FDI and shows the Universal number.
    assert 'data-dente="36"' in page and ">19</button>" in page
    assert "Numeração universal (Estados Unidos)." in page
