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
from tests.test_finance import TODAY, entry_with, installments_of, log_in, scenario  # noqa: F401

pytestmark = pytest.mark.django_db


def change_country(data, country):
    clinic = data["clinic"]
    clinic.country = country
    clinic.save()


def test_each_country_has_its_methods():
    assert set(payment_methods.METHODS) == set(COUNTRIES)
    for country, for_country in payment_methods.METHODS.items():
        assert len(set(for_country.codes)) == len(for_country.codes), country
        assert set(for_country.codes) <= set(Payment.Method.values), country
        assert {"dinheiro", "credito", "transferencia"} <= set(for_country.codes), country
        assert set(for_country.names) <= set(for_country.codes), country


def test_local_names_in_parentheses():
    with translation.override("pt-br"):
        assert payment_methods.label("transferencia", "MX") == "Transferência (SPEI)"
        assert payment_methods.label("carteira", "PE") == "Carteira digital (Yape, Plin)"
        assert payment_methods.label("transferencia", "BR") == "Transferência"
        # Brazil keeps its methods, in the same order, and still no cheque.
        assert [code for code, _name in payment_methods.in_use("BR")] == [
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
    for variant in ("en-gb", "en-ca", "en-au", "en-za"):
        with translation.override(variant):
            assert payment_methods.label("cheque", "GB") == "Cheque", variant
    with translation.override("es"):
        assert payment_methods.label("cheque", "MX") == "Cheque"


def test_form_offers_the_country_methods(scenario):  # noqa: F811
    change_country(scenario, "PE")
    entry = entry_with(scenario, amount="100.00", installments=1)
    installment = installments_of(scenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    admin = log_in(scenario, "admin")
    page = admin.get(url).content.decode()
    assert 'value="carteira"' in page and "Yape, Plin" in page
    assert 'value="pix"' not in page and 'value="boleto"' not in page
    data = {"date": TODAY.isoformat(), "amount": "100", "account": scenario["cash_register"].pk}
    assert "method" in admin.post(url, {**data, "method": "pix"}).context["form"].errors
    assert admin.post(url, {**data, "method": "carteira"}).status_code == 302
    with use_clinic(scenario["clinic"]), translation.override("pt-br"):
        payment = Payment.objects.get()
        assert payment.get_method_display() == "Carteira digital (Yape, Plin)"
        report = services.report(TODAY, TODAY)
    assert report["by_method"] == [("Carteira digital (Yape, Plin)", Decimal("100.00"))]
    new_one = admin.get(reverse("finance:entry_new")).content.decode()
    assert 'value="carteira"' in new_one and 'value="pix"' not in new_one


def test_card_without_installments_in_united_states(scenario):  # noqa: F811
    entry = entry_with(scenario, amount="100.00", installments=1)
    installment = installments_of(scenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    admin = log_in(scenario, "admin")
    form = admin.get(url).context["form"]
    assert "card_installments" in form.fields and "NSU" in str(
        form.fields["card_transaction_code"].label
    )

    change_country(scenario, "US")
    form = admin.get(url).context["form"]
    assert "card_installments" not in form.fields
    assert "NSU" not in str(form.fields["card_transaction_code"].label)
    data = {
        "date": TODAY.isoformat(),
        "amount": "100",
        "account": scenario["cash_register"].pk,
        "method": "hsa",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert admin.post(url, data).status_code == 302
    with use_clinic(scenario["clinic"]):
        payment = Payment.objects.get()
    # An HSA/FSA card is a card: its details are kept, but not installments.
    assert (payment.card_brand, payment.card_transaction_code) == ("Visa", "A1B2")
    assert payment.card_installments is None


def test_card_details_only_for_card(scenario):  # noqa: F811
    entry = entry_with(scenario, amount="100.00", installments=1)
    installment = installments_of(scenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    data = {
        "date": TODAY.isoformat(),
        "amount": "100",
        "account": scenario["cash_register"].pk,
        "method": "pix",
        "card_brand": "Visa",
        "card_installments": "3",
        "card_transaction_code": "A1B2",
    }
    assert log_in(scenario, "admin").post(url, data).status_code == 302
    with use_clinic(scenario["clinic"]):
        payment = Payment.objects.get()
    assert (payment.card_brand, payment.card_installments, payment.card_transaction_code) == (
        "",
        None,
        "",
    )


def test_old_payment_shows_method_the_country_no_longer_offers(scenario):  # noqa: F811
    entry = entry_with(scenario, amount="100.00", installments=1)
    with use_clinic(scenario["clinic"]), translation.override("pt-br"):
        payment = services.receive(
            installments_of(scenario, entry)[0],
            user=scenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=scenario["cash_register"],
        )
        change_country(scenario, "US")
        assert payment.get_method_display() == "Pix"
        assert services.report(TODAY, TODAY)["by_method"] == [("Pix", Decimal("100.00"))]
