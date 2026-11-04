"""Payment methods of each country (decision 123): each country offers its own, with the local
systems' names, and card installments only where card issuers split payments."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core.countries import PAISES
from apps.core.isolation import usar_clinica
from apps.finance import payment_methods, services
from apps.finance.models import Pagamento
from tests.test_finance import HOJE, cenario, entrar, lancamento_com, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def mudar_pais(dados, pais):
    clinica = dados["clinica"]
    clinica.pais = pais
    clinica.save()


def test_cada_pais_tem_as_suas_formas():
    assert set(payment_methods.FORMAS) == set(PAISES)
    for pais, do_pais in payment_methods.FORMAS.items():
        assert len(set(do_pais.codigos)) == len(do_pais.codigos), pais
        assert set(do_pais.codigos) <= set(Pagamento.Forma.values), pais
        assert {"dinheiro", "credito", "transferencia"} <= set(do_pais.codigos), pais
        assert set(do_pais.nomes) <= set(do_pais.codigos), pais


def test_nomes_locais_entre_parenteses():
    with translation.override("pt-br"):
        assert payment_methods.rotulo("transferencia", "MX") == "Transferência (SPEI)"
        assert payment_methods.rotulo("carteira", "PE") == "Carteira digital (Yape, Plin)"
        assert payment_methods.rotulo("transferencia", "BR") == "Transferência"
        # Brazil keeps its methods, in the same order, and still no cheque.
        assert [codigo for codigo, _nome in payment_methods.em_uso("BR")] == [
            "dinheiro",
            "pix",
            "debito",
            "credito",
            "transferencia",
            "boleto",
        ]
    with translation.override("en"):
        # The local name is not repeated when it is the translated name itself.
        assert payment_methods.rotulo("debito_auto", "GB") == "Direct debit"
        assert payment_methods.rotulo("debito_auto", "ZA") == "Direct debit (debit order)"


def test_cheque_com_a_grafia_de_cada_ingles():
    with translation.override("en"):
        assert payment_methods.rotulo("cheque", "US") == "Check"
    for variante in ("en-gb", "en-ca", "en-au", "en-za"):
        with translation.override(variante):
            assert payment_methods.rotulo("cheque", "GB") == "Cheque", variante
    with translation.override("es"):
        assert payment_methods.rotulo("cheque", "MX") == "Cheque"


def test_formulario_oferece_as_formas_do_pais(cenario):  # noqa: F811
    mudar_pais(cenario, "PE")
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    url = reverse("finance:receive_installment", args=[parcela.pk])
    admin = entrar(cenario, "admin")
    pagina = admin.get(url).content.decode()
    assert 'value="carteira"' in pagina and "Yape, Plin" in pagina
    assert 'value="pix"' not in pagina and 'value="boleto"' not in pagina
    dados = {"data": HOJE.isoformat(), "valor": "100", "conta": cenario["caixa"].pk}
    assert "forma" in admin.post(url, {**dados, "forma": "pix"}).context["form"].errors
    assert admin.post(url, {**dados, "forma": "carteira"}).status_code == 302
    with usar_clinica(cenario["clinica"]), translation.override("pt-br"):
        pagamento = Pagamento.objects.get()
        assert pagamento.get_forma_display() == "Carteira digital (Yape, Plin)"
        relatorio = services.relatorio(HOJE, HOJE)
    assert relatorio["por_forma"] == [("Carteira digital (Yape, Plin)", Decimal("100.00"))]
    nova = admin.get(reverse("finance:entry_new")).content.decode()
    assert 'value="carteira"' in nova and 'value="pix"' not in nova


def test_cartao_sem_parcelas_nos_estados_unidos(cenario):  # noqa: F811
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    url = reverse("finance:receive_installment", args=[parcela.pk])
    admin = entrar(cenario, "admin")
    form = admin.get(url).context["form"]
    assert "cartao_parcelas" in form.fields and "NSU" in str(form.fields["cartao_codigo"].label)

    mudar_pais(cenario, "US")
    form = admin.get(url).context["form"]
    assert "cartao_parcelas" not in form.fields
    assert "NSU" not in str(form.fields["cartao_codigo"].label)
    dados = {
        "data": HOJE.isoformat(),
        "valor": "100",
        "conta": cenario["caixa"].pk,
        "forma": "hsa",
        "cartao_bandeira": "Visa",
        "cartao_parcelas": "3",
        "cartao_codigo": "A1B2",
    }
    assert admin.post(url, dados).status_code == 302
    with usar_clinica(cenario["clinica"]):
        pagamento = Pagamento.objects.get()
    # An HSA/FSA card is a card: its details are kept, but not installments.
    assert (pagamento.cartao_bandeira, pagamento.cartao_codigo) == ("Visa", "A1B2")
    assert pagamento.cartao_parcelas is None


def test_detalhes_do_cartao_so_para_cartao(cenario):  # noqa: F811
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    url = reverse("finance:receive_installment", args=[parcela.pk])
    dados = {
        "data": HOJE.isoformat(),
        "valor": "100",
        "conta": cenario["caixa"].pk,
        "forma": "pix",
        "cartao_bandeira": "Visa",
        "cartao_parcelas": "3",
        "cartao_codigo": "A1B2",
    }
    assert entrar(cenario, "admin").post(url, dados).status_code == 302
    with usar_clinica(cenario["clinica"]):
        pagamento = Pagamento.objects.get()
    assert (pagamento.cartao_bandeira, pagamento.cartao_parcelas, pagamento.cartao_codigo) == (
        "",
        None,
        "",
    )


def test_pagamento_antigo_mostra_a_forma_que_o_pais_nao_oferece(cenario):  # noqa: F811
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    with usar_clinica(cenario["clinica"]), translation.override("pt-br"):
        pagamento = services.receber(
            parcelas_de(cenario, lancamento)[0],
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
        )
        mudar_pais(cenario, "US")
        assert pagamento.get_forma_display() == "Pix"
        assert services.relatorio(HOJE, HOJE)["por_forma"] == [("Pix", Decimal("100.00"))]
