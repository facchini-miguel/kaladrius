"""Payment methods of each country (decision 123): each country offers its own, with the local
systems' names, and card installments only where card issuers split payments."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core.countries import PAISES
from apps.core.isolation import usar_clinica
from apps.finance import payment_methods, services
from apps.finance.models import Payment
from tests.test_finance import HOJE, cenario, entrar, lancamento_com, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def mudar_pais(dados, country):
    clinic = dados["clinic"]
    clinic.country = country
    clinic.save()


def test_cada_pais_tem_as_suas_formas():
    assert set(payment_methods.FORMAS) == set(PAISES)
    for country, do_pais in payment_methods.FORMAS.items():
        assert len(set(do_pais.codigos)) == len(do_pais.codigos), country
        assert set(do_pais.codigos) <= set(Payment.Forma.values), country
        assert {"dinheiro", "credito", "transferencia"} <= set(do_pais.codigos), country
        assert set(do_pais.nomes) <= set(do_pais.codigos), country


def test_nomes_locais_entre_parenteses():
    with translation.override("pt-br"):
        assert payment_methods.rotulo("transferencia", "MX") == "Transferência (SPEI)"
        assert payment_methods.rotulo("carteira", "PE") == "Carteira digital (Yape, Plin)"
        assert payment_methods.rotulo("transferencia", "BR") == "Transferência"
        # Brazil keeps its methods, in the same order, and still no cheque.
        assert [code for code, _nome in payment_methods.em_uso("BR")] == [
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
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    admin = entrar(cenario, "admin")
    pagina = admin.get(url).content.decode()
    assert 'value="carteira"' in pagina and "Yape, Plin" in pagina
    assert 'value="pix"' not in pagina and 'value="boleto"' not in pagina
    dados = {"date": HOJE.isoformat(), "amount": "100", "account": cenario["cash_register"].pk}
    assert "method" in admin.post(url, {**dados, "method": "pix"}).context["form"].errors
    assert admin.post(url, {**dados, "method": "carteira"}).status_code == 302
    with usar_clinica(cenario["clinic"]), translation.override("pt-br"):
        payment = Payment.objects.get()
        assert payment.get_method_display() == "Carteira digital (Yape, Plin)"
        relatorio = services.relatorio(HOJE, HOJE)
    assert relatorio["por_forma"] == [("Carteira digital (Yape, Plin)", Decimal("100.00"))]
    nova = admin.get(reverse("finance:entry_new")).content.decode()
    assert 'value="carteira"' in nova and 'value="pix"' not in nova


def test_cartao_sem_parcelas_nos_estados_unidos(cenario):  # noqa: F811
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    admin = entrar(cenario, "admin")
    form = admin.get(url).context["form"]
    assert "card_installments" in form.fields and "NSU" in str(
        form.fields["card_transaction_code"].label
    )

    mudar_pais(cenario, "US")
    form = admin.get(url).context["form"]
    assert "card_installments" not in form.fields
    assert "NSU" not in str(form.fields["card_transaction_code"].label)
    dados = {
        "date": HOJE.isoformat(),
        "amount": "100",
        "account": cenario["cash_register"].pk,
        "method": "hsa",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert admin.post(url, dados).status_code == 302
    with usar_clinica(cenario["clinic"]):
        payment = Payment.objects.get()
    # An HSA/FSA card is a card: its details are kept, but not installments.
    assert (payment.card_brand, payment.card_transaction_code) == ("Visa", "A1B2")
    assert payment.card_installments is None


def test_detalhes_do_cartao_so_para_cartao(cenario):  # noqa: F811
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    dados = {
        "date": HOJE.isoformat(),
        "amount": "100",
        "account": cenario["cash_register"].pk,
        "method": "pix",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert entrar(cenario, "admin").post(url, dados).status_code == 302
    with usar_clinica(cenario["clinic"]):
        payment = Payment.objects.get()
    assert (payment.card_brand, payment.card_installments, payment.card_transaction_code) == (
        "",
        None,
        "",
    )


def test_pagamento_antigo_mostra_a_forma_que_o_pais_nao_oferece(cenario):  # noqa: F811
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    with usar_clinica(cenario["clinic"]), translation.override("pt-br"):
        payment = services.receber(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=cenario["cash_register"],
        )
        mudar_pais(cenario, "US")
        assert payment.get_method_display() == "Pix"
        assert services.relatorio(HOJE, HOJE)["por_forma"] == [("Pix", Decimal("100.00"))]
