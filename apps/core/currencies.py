"""The clinic's currency (decision 114): chosen by the clinic administrator, independent of each
user's language. Amounts are stored as plain numbers, so the currency only changes how they are
shown; nothing is ever converted.

The symbol and the number of decimals come from the currency; the thousands and decimal
separators come from the user's language (R$ 1.234,56 in Portuguese, R$ 1,234.56 in English).
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.utils.formats import get_format, number_format
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

DEFAULT = "BRL"

# ISO 4217 code: (name, symbol, decimals). The symbol is the one people write in the
# currency's own country; "$" is enough because a clinic works in a single currency.
CURRENCIES = {
    "BRL": (_("Real brasileiro"), "R$", 2),
    "USD": (_("Dólar americano"), "US$", 2),
    "EUR": (_("Euro"), "€", 2),
    "GBP": (_("Libra esterlina"), "£", 2),
    "CAD": (_("Dólar canadense"), "$", 2),
    "AUD": (_("Dólar australiano"), "$", 2),
    "ZAR": (_("Rand sul-africano"), "R", 2),
    "ARS": (_("Peso argentino"), "$", 2),
    "MXN": (_("Peso mexicano"), "$", 2),
    "CLP": (_("Peso chileno"), "$", 0),
    "COP": (_("Peso colombiano"), "$", 2),
    "UYU": (_("Peso uruguaio"), "$U", 2),
    "PYG": (_("Guarani paraguaio"), "₲", 0),
    "PEN": (_("Sol peruano"), "S/", 2),
    "BOB": (_("Boliviano"), "Bs", 2),
}

CHOICES = [
    (code, format_lazy("{} ({}, {})", name, symbol, code))
    for code, (name, symbol, _places) in CURRENCIES.items()
]


# Longest first, so "US$" goes before "$".
SYMBOLS = sorted({symbol for _nome, symbol, _places in CURRENCIES.values()}, key=len, reverse=True)


def clinic_currency():
    """Code of the current clinic's currency (the real when there is no current clinic)."""
    from .isolation import current_clinic

    clinic = current_clinic()
    return getattr(clinic, "currency", None) or DEFAULT


def format_amount(value, code=None):
    """The amount with the currency symbol, e.g. R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €.
    The euro goes after the number in languages with a decimal comma (Portugal, Spain)."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    _nome, symbol, places = CURRENCIES.get(code or clinic_currency(), CURRENCIES[DEFAULT])
    # Rounded like money (Django's number_format just cuts the extra decimals).
    value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    number = number_format(value, places, force_grouping=True)
    if symbol == "€" and get_format("DECIMAL_SEPARATOR") == ",":
        return f"{number} {symbol}"
    return f"{symbol} {number}"


def symbol():
    """Symbol of the current clinic's currency, for labels and examples."""
    return CURRENCIES.get(clinic_currency(), CURRENCIES[DEFAULT])[1]
