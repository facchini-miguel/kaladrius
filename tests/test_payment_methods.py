"""Payment methods of each country (decision 123): each country offers its own, with the local
systems' names, and card installments only where card issuers split payments."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core.countries import COUNTRIES
from apps.core.isolation import use_clinic
from apps.finance import payment_methods, services
from apps.finance.models import Payment
from tests.test_finance import HOJE, cenario, entrar, lancamento_com, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def mudar_pais(data, country):
    clinic = data["clinic"]
    clinic.country = country
    clinic.save()


def test_each_country_has_its_methods():
    assert set(payment_methods.METHODS) == set(COUNTRIES)
    for country, for_country in payment_methods.METHODS.items():
        assert len(set(for_country.codigos)) == len(for_country.codigos), country
        assert set(for_country.codigos) <= set(Payment.Method.values), country
        assert {"dinheiro", "credito", "transferencia"} <= set(for_country.codigos), country
        assert set(for_country.nomes) <= set(for_country.codigos), country


def test_local_names_in_parentheses():
    with translation.override("pt-br"):
        assert payment_methods.label("transferencia", "MX") == "Transferência (SPEI)"
        assert payment_methods.label("carteira", "PE") == "Carteira digital (Yape, Plin)"
        assert payment_methods.label("transferencia", "BR") == "Transferência"
        # Brazil keeps its methods, in the same order, and still no cheque.
        assert [code for code, _nome in payment_methods.in_use("BR")] == [
            "dinheiro",
            "pix",
            "debito",
            "credito",
            "transferencia",
            "boleto",
        ]
    with translation.override("en"):
        # The local name is not repeated when it is the translated name itself.
        assert payment_methods.label("debito_auto", "GB") == "Direct debit"
        assert payment_methods.label("debito_auto", "ZA") == "Direct debit (debit order)"


def test_check_spelled_per_english_variant():
    with translation.override("en"):
        assert payment_methods.label("cheque", "US") == "Check"
    for variante in ("en-gb", "en-ca", "en-au", "en-za"):
        with translation.override(variante):
            assert payment_methods.label("cheque", "GB") == "Cheque", variante
    with translation.override("es"):
        assert payment_methods.label("cheque", "MX") == "Cheque"


def test_form_offers_the_country_methods(cenario):  # noqa: F811
    mudar_pais(cenario, "PE")
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    admin = entrar(cenario, "admin")
    page = admin.get(url).content.decode()
    assert 'value="carteira"' in page and "Yape, Plin" in page
    assert 'value="pix"' not in page and 'value="boleto"' not in page
    data = {"date": HOJE.isoformat(), "amount": "100", "account": cenario["cash_register"].pk}
    assert "method" in admin.post(url, {**data, "method": "pix"}).context["form"].errors
    assert admin.post(url, {**data, "method": "carteira"}).status_code == 302
    with use_clinic(cenario["clinic"]), translation.override("pt-br"):
        payment = Payment.objects.get()
        assert payment.get_method_display() == "Carteira digital (Yape, Plin)"
        report = services.report(HOJE, HOJE)
    assert report["por_forma"] == [("Carteira digital (Yape, Plin)", Decimal("100.00"))]
    nova = admin.get(reverse("finance:entry_new")).content.decode()
    assert 'value="carteira"' in nova and 'value="pix"' not in nova


def test_card_without_installments_in_united_states(cenario):  # noqa: F811
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
    data = {
        "date": HOJE.isoformat(),
        "amount": "100",
        "account": cenario["cash_register"].pk,
        "method": "hsa",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert admin.post(url, data).status_code == 302
    with use_clinic(cenario["clinic"]):
        payment = Payment.objects.get()
    # An HSA/FSA card is a card: its details are kept, but not installments.
    assert (payment.card_brand, payment.card_transaction_code) == ("Visa", "A1B2")
    assert payment.card_installments is None


def test_card_details_only_for_card(cenario):  # noqa: F811
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    data = {
        "date": HOJE.isoformat(),
        "amount": "100",
        "account": cenario["cash_register"].pk,
        "method": "pix",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert entrar(cenario, "admin").post(url, data).status_code == 302
    with use_clinic(cenario["clinic"]):
        payment = Payment.objects.get()
    assert (payment.card_brand, payment.card_installments, payment.card_transaction_code) == (
        "",
        None,
        "",
    )


def test_old_payment_shows_method_the_country_no_longer_offers(cenario):  # noqa: F811
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    with use_clinic(cenario["clinic"]), translation.override("pt-br"):
        payment = services.receive(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=cenario["cash_register"],
        )
        mudar_pais(cenario, "US")
        assert payment.get_method_display() == "Pix"
        assert services.report(HOJE, HOJE)["por_forma"] == [("Pix", Decimal("100.00"))]
