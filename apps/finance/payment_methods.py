"""Payment methods of each country (decision 123), phase 4 of the internationalization.

Every method is one code of `Pagamento.Forma` with a generic, translated name ("Transferência",
"Carteira digital"); a country lists the ones its clinics are offered, in order, and may add
the local systems' own names, which are not translated: "Transferência (SPEI)" in Mexico,
"Carteira digital (Yape, Plin)" in Peru. Payments keep their code, so a method a country no
longer offers (Brazil's cheque) still shows on old payments.
"""

from dataclasses import dataclass, field

from django.utils import translation

from apps.core import countries

CASH = "cash"
PIX = "pix"
DEBIT = "debit"
CREDIT = "credit"
TRANSFER = "transfer"
BOLETO = "boleto"
CHEQUE = "cheque"
WALLET = "wallet"  # digital wallet or QR code
DIRECT_DEBIT = "direct_debit"  # direct debit, pre-authorized debit, debit order
HSA = "hsa"  # HSA/FSA card (United States)
FINANCING = "financing"  # patient financing
BPAY = "bpay"  # bill payment (Australia)

# Methods paid with a card: the card details (brand, transaction code) apply to them.
CARDS = frozenset({DEBIT, CREDIT, HSA})


@dataclass(frozen=True)
class Methods:
    codes: tuple
    names: dict = field(default_factory=dict)  # code → local systems, shown in parentheses
    card_installments: bool = True  # card payments split by the card issuer (cuotas)
    card_code: str = ""  # local name of the card transaction code (NSU in Brazil)


# Latin America: cash, cards (paid in installments, "cuotas"), transfer and the wallets.
_LATIN = (CASH, DEBIT, CREDIT, TRANSFER, WALLET)

METHODS = {
    "BR": Methods((CASH, PIX, DEBIT, CREDIT, TRANSFER, BOLETO), card_code="NSU"),
    "MX": Methods((*_LATIN, CHEQUE), {TRANSFER: "SPEI", WALLET: "Mercado Pago, CoDi"}),
    "AR": Methods((*_LATIN, CHEQUE), {WALLET: "Mercado Pago, MODO"}),
    "CL": Methods((*_LATIN, CHEQUE), {DEBIT: "Redcompra", WALLET: "Mercado Pago, MACH"}),
    "CO": Methods(_LATIN, {TRANSFER: "PSE, Bre-B", WALLET: "Nequi, Daviplata"}),
    "PE": Methods(_LATIN, {WALLET: "Yape, Plin"}),
    "UY": Methods(_LATIN, {WALLET: "Mercado Pago"}),
    "PY": Methods(_LATIN, {TRANSFER: "SIPAP", WALLET: "QR"}),
    "BO": Methods(_LATIN, {WALLET: "QR"}),
    "EC": Methods(_LATIN, {WALLET: "Deuna, QR"}),
    # English-speaking countries: no card installments; cheques where they are still used.
    "US": Methods(
        (CASH, CHEQUE, DEBIT, CREDIT, HSA, TRANSFER, WALLET, FINANCING),
        {TRANSFER: "ACH", WALLET: "Zelle, Venmo"},
        card_installments=False,
    ),
    "GB": Methods(
        (CASH, DEBIT, CREDIT, TRANSFER, DIRECT_DEBIT, CHEQUE),
        {TRANSFER: "Faster Payments", DIRECT_DEBIT: "Direct Debit"},
        card_installments=False,
    ),
    "CA": Methods(
        (CASH, DEBIT, CREDIT, TRANSFER, DIRECT_DEBIT, CHEQUE, FINANCING),
        {DEBIT: "Interac", TRANSFER: "Interac e-Transfer", DIRECT_DEBIT: "PAD"},
        card_installments=False,
    ),
    "AU": Methods(
        (CASH, DEBIT, CREDIT, TRANSFER, BPAY, DIRECT_DEBIT, FINANCING),
        {DEBIT: "EFTPOS", TRANSFER: "PayID"},
        card_installments=False,
    ),
    "ZA": Methods(
        (CASH, DEBIT, CREDIT, TRANSFER, WALLET, DIRECT_DEBIT),
        {TRANSFER: "EFT", WALLET: "SnapScan, Zapper", DIRECT_DEBIT: "debit order"},
        card_installments=False,
    ),
}


def for_country(country=None):
    """The methods of `pais`, or of the current clinic's country."""
    return METHODS.get(country or countries.clinic_country(), METHODS[countries.DEFAULT])


# The English variants other than the United States' (en-gb, en-ca, en-au, en-za) spell it
# "cheque"; the English catalog has the American "check".
_ENGLISH_WITH_CHEQUE = {country.english for country in countries.COUNTRIES.values()} - {"en"}


def label(code, country=None):
    """The method's name in the country: "Transferência (SPEI)" in Mexico."""
    from .models import Payment

    name = dict(Payment.Method.choices).get(code, code)
    if code == CHEQUE and translation.get_language() in _ENGLISH_WITH_CHEQUE:
        name = "Cheque"
    local = for_country(country).names.get(code)
    if not local or local.lower() == str(name).lower():  # "Direct debit" in English
        return str(name)
    return f"{name} ({local})"


def in_use(country=None):
    """(code, name) of the methods offered when recording a payment."""
    return [(code, label(code, country)) for code in for_country(country).codes]


def labels(country=None):
    """code → name of every method, for the reports (old payments included)."""
    from .models import Payment

    return {code: label(code, country) for code in Payment.Method.values}
