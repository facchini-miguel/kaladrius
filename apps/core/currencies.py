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

PADRAO = "BRL"

# ISO 4217 code: (name, symbol, decimals). The symbol is the one people write in the
# currency's own country; "$" is enough because a clinic works in a single currency.
MOEDAS = {
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

ESCOLHAS = [
    (codigo, format_lazy("{} ({}, {})", nome, simbolo, codigo))
    for codigo, (nome, simbolo, _casas) in MOEDAS.items()
]


# Longest first, so "US$" goes before "$".
SIMBOLOS = sorted({simbolo for _nome, simbolo, _casas in MOEDAS.values()}, key=len, reverse=True)


def moeda_da_clinica():
    """Code of the current clinic's currency (the real when there is no current clinic)."""
    from .isolation import clinica_atual

    clinica = clinica_atual()
    return getattr(clinica, "moeda", None) or PADRAO


def formatar(valor, codigo=None):
    """The amount with the currency symbol, e.g. R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €.
    The euro goes after the number in languages with a decimal comma (Portugal, Spain)."""
    try:
        valor = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    _nome, simbolo, casas = MOEDAS.get(codigo or moeda_da_clinica(), MOEDAS[PADRAO])
    # Rounded like money (Django's number_format just cuts the extra decimals).
    valor = valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    numero = number_format(valor, casas, force_grouping=True)
    if simbolo == "€" and get_format("DECIMAL_SEPARATOR") == ",":
        return f"{numero} {simbolo}"
    return f"{simbolo} {numero}"


def simbolo():
    """Symbol of the current clinic's currency, for labels and examples."""
    return MOEDAS.get(moeda_da_clinica(), MOEDAS[PADRAO])[1]
