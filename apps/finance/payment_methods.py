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

DINHEIRO = "dinheiro"
PIX = "pix"
DEBITO = "debito"
CREDITO = "credito"
TRANSFERENCIA = "transferencia"
BOLETO = "boleto"
CHEQUE = "cheque"
CARTEIRA = "carteira"  # digital wallet or QR code
DEBITO_AUTOMATICO = "debito_auto"  # direct debit, pre-authorized debit, debit order
HSA = "hsa"  # HSA/FSA card (United States)
FINANCIAMENTO = "financiamento"  # patient financing
BPAY = "bpay"  # bill payment (Australia)

# Methods paid with a card: the card details (brand, transaction code) apply to them.
CARTOES = frozenset({DEBITO, CREDITO, HSA})


@dataclass(frozen=True)
class Formas:
    codigos: tuple
    nomes: dict = field(default_factory=dict)  # code → local systems, shown in parentheses
    parcelas_no_cartao: bool = True  # card payments split by the card issuer (cuotas)
    codigo_do_cartao: str = ""  # local name of the card transaction code (NSU in Brazil)


# Latin America: cash, cards (paid in installments, "cuotas"), transfer and the wallets.
_LATINA = (DINHEIRO, DEBITO, CREDITO, TRANSFERENCIA, CARTEIRA)

FORMAS = {
    "BR": Formas((DINHEIRO, PIX, DEBITO, CREDITO, TRANSFERENCIA, BOLETO), codigo_do_cartao="NSU"),
    "MX": Formas((*_LATINA, CHEQUE), {TRANSFERENCIA: "SPEI", CARTEIRA: "Mercado Pago, CoDi"}),
    "AR": Formas((*_LATINA, CHEQUE), {CARTEIRA: "Mercado Pago, MODO"}),
    "CL": Formas((*_LATINA, CHEQUE), {DEBITO: "Redcompra", CARTEIRA: "Mercado Pago, MACH"}),
    "CO": Formas(_LATINA, {TRANSFERENCIA: "PSE, Bre-B", CARTEIRA: "Nequi, Daviplata"}),
    "PE": Formas(_LATINA, {CARTEIRA: "Yape, Plin"}),
    "UY": Formas(_LATINA, {CARTEIRA: "Mercado Pago"}),
    "PY": Formas(_LATINA, {TRANSFERENCIA: "SIPAP", CARTEIRA: "QR"}),
    "BO": Formas(_LATINA, {CARTEIRA: "QR"}),
    "EC": Formas(_LATINA, {CARTEIRA: "Deuna, QR"}),
    # English-speaking countries: no card installments; cheques where they are still used.
    "US": Formas(
        (DINHEIRO, CHEQUE, DEBITO, CREDITO, HSA, TRANSFERENCIA, CARTEIRA, FINANCIAMENTO),
        {TRANSFERENCIA: "ACH", CARTEIRA: "Zelle, Venmo"},
        parcelas_no_cartao=False,
    ),
    "GB": Formas(
        (DINHEIRO, DEBITO, CREDITO, TRANSFERENCIA, DEBITO_AUTOMATICO, CHEQUE),
        {TRANSFERENCIA: "Faster Payments", DEBITO_AUTOMATICO: "Direct Debit"},
        parcelas_no_cartao=False,
    ),
    "CA": Formas(
        (DINHEIRO, DEBITO, CREDITO, TRANSFERENCIA, DEBITO_AUTOMATICO, CHEQUE, FINANCIAMENTO),
        {DEBITO: "Interac", TRANSFERENCIA: "Interac e-Transfer", DEBITO_AUTOMATICO: "PAD"},
        parcelas_no_cartao=False,
    ),
    "AU": Formas(
        (DINHEIRO, DEBITO, CREDITO, TRANSFERENCIA, BPAY, DEBITO_AUTOMATICO, FINANCIAMENTO),
        {DEBITO: "EFTPOS", TRANSFERENCIA: "PayID"},
        parcelas_no_cartao=False,
    ),
    "ZA": Formas(
        (DINHEIRO, DEBITO, CREDITO, TRANSFERENCIA, CARTEIRA, DEBITO_AUTOMATICO),
        {TRANSFERENCIA: "EFT", CARTEIRA: "SnapScan, Zapper", DEBITO_AUTOMATICO: "debit order"},
        parcelas_no_cartao=False,
    ),
}


def do_pais(pais=None):
    """The methods of `pais`, or of the current clinic's country."""
    return FORMAS.get(pais or countries.pais_da_clinica(), FORMAS[countries.PADRAO])


# The English variants other than the United States' (en-gb, en-ca, en-au, en-za) spell it
# "cheque"; the English catalog has the American "check".
_INGLES_COM_CHEQUE = {pais.ingles for pais in countries.PAISES.values()} - {"en"}


def rotulo(codigo, pais=None):
    """The method's name in the country: "Transferência (SPEI)" in Mexico."""
    from .models import Payment

    nome = dict(Payment.Forma.choices).get(codigo, codigo)
    if codigo == CHEQUE and translation.get_language() in _INGLES_COM_CHEQUE:
        nome = "Cheque"
    local = do_pais(pais).nomes.get(codigo)
    if not local or local.lower() == str(nome).lower():  # "Direct debit" in English
        return str(nome)
    return f"{nome} ({local})"


def em_uso(pais=None):
    """(code, name) of the methods offered when recording a payment."""
    return [(codigo, rotulo(codigo, pais)) for codigo in do_pais(pais).codigos]


def rotulos(pais=None):
    """code → name of every method, for the reports (old payments included)."""
    from .models import Payment

    return {codigo: rotulo(codigo, pais) for codigo in Payment.Forma.values}
