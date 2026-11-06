"""The clinic's currency (decision 114): set by the clinic administrator, independent of each
user's language; amounts are shown in it and never converted."""

from decimal import Decimal

import pytest
from django import forms
from django.template import Context, Template
from django.urls import reverse
from django.utils import translation

from apps.core import currencies
from apps.core.forms import LocalizedDecimalField
from apps.core.isolation import use_clinic
from apps.core.models import Role
from tests.test_core import clinic_data

pytestmark = pytest.mark.django_db

AMOUNT = Decimal("1234.56")


@pytest.mark.parametrize(
    ("code", "language", "expected"),
    [
        ("BRL", "pt-br", "R$ 1.234,56"),
        ("BRL", "en", "R$ 1,234.56"),
        ("USD", "en", "US$ 1,234.56"),
        ("USD", "pt-br", "US$ 1.234,56"),
        ("EUR", "es", "1\u00a0234,56 €"),  # after the number with a decimal comma
        ("EUR", "pt-br", "1.234,56 €"),
        ("EUR", "en", "€ 1,234.56"),
        ("MXN", "es", "$ 1\u00a0234,56"),  # Spanish groups with a narrow space
        ("CLP", "es", "$ 1\u00a0235"),  # no cents, rounded
        ("PYG", "en", "₲ 1,235"),
        ("UYU", "es", "$U 1\u00a0234,56"),
    ],
)
def test_currency_symbol_and_language_separators(code, language, expected):
    with translation.override(language):
        assert currencies.format_amount(AMOUNT, code) == expected


def test_invalid_amount_stays_empty():
    assert currencies.format_amount(None, "USD") == ""
    assert currencies.format_amount("abc", "USD") == ""


def test_filter_uses_the_current_clinic_currency(clinic_a):
    template_ = Template("{% load formats %}{{ amount|currency }} {% currency_symbol %}")
    context = Context({"amount": AMOUNT})
    with translation.override("pt-br"):
        assert template_.render(context) == "R$ 1.234,56 R$"  # no current clinic: the real
        clinic_a.currency = "EUR"
        with use_clinic(clinic_a):
            assert template_.render(context) == "1.234,56 € €"


def test_admin_picks_currency_and_amounts_show_in_it(clinic_a, create_user, client_for):
    assert clinic_a.currency == "BRL"  # existing and new clinics start with the real
    admin = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    assert "Dólar americano (US$, USD)" in admin.get(reverse("clinic_settings")).content.decode()

    response = admin.post(reverse("clinic_settings"), clinic_data(currency="USD"), follow=True)
    page = response.content.decode()
    assert "Nenhum valor já lançado foi convertido" in page
    clinic_a.refresh_from_db()
    assert clinic_a.currency == "USD"

    # The language stays each user's own: the currency follows the clinic in any of them.
    admin.post(reverse("change_language"), {"language": "es"})
    assert "US$ 0,00" in admin.get(reverse("home")).content.decode()  # received today

    # Saving again without changing it does not repeat the warning.
    admin.post(reverse("change_language"), {"language": "pt-br"})
    response = admin.post(reverse("clinic_settings"), clinic_data(currency="USD"), follow=True)
    assert "Nenhum valor já lançado foi convertido" not in response.content.decode()


def test_unknown_currency_is_refused(clinic_a, create_user, client_for):
    admin = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    response = admin.post(reverse("clinic_settings"), clinic_data(currency="XXX"))
    assert response.status_code == 200 and "currency" in response.context["form"].errors


def test_only_admin_changes_the_currency(clinic_a, create_user, client_for):
    reception = client_for(create_user("recepcao_a", clinic_a, Role.FRONT_DESK))
    assert (
        reception.post(reverse("clinic_settings"), clinic_data(currency="EUR")).status_code == 403
    )
    clinic_a.refresh_from_db()
    assert clinic_a.currency == "BRL"


@pytest.mark.parametrize("typed", ["US$ 1.500,00", "€ 1.500", "1.500 €", "$U 1.500,00", "S/ 1500"])
def test_amount_typed_with_any_currency_symbol(typed):
    with translation.override("pt-br"):
        assert LocalizedDecimalField(decimal_places=2, localize=True).clean(typed) == Decimal(
            "1500.00"
        )


def test_text_that_is_not_an_amount_is_still_refused():
    with translation.override("pt-br"), pytest.raises(forms.ValidationError):
        LocalizedDecimalField(decimal_places=2, localize=True).clean("abc")


def test_form_without_currency_keeps_the_current(clinic_a, create_user, client_for):
    """A settings page opened before the update does not send the currency."""
    clinic_a.currency = "EUR"
    clinic_a.save(update_fields=["currency"])
    admin = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    data = clinic_data()
    del data["currency"]
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    clinic_a.refresh_from_db()
    assert clinic_a.currency == "EUR"
