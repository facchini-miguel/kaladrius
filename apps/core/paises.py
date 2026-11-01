"""The clinic's country (decision 117): time zone, phones, postal codes, the English variant
of dates and the default currency. Brazil keeps every rule it had; the other countries start
with the English-speaking markets (United States, United Kingdom, Canada, Australia and South
Africa). Documents (CPF/CNPJ and each country's own) are phase 2 of the internationalization.
"""

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

PADRAO = "BR"


@dataclass(frozen=True)
class Pais:
    nome: str
    ddi: str  # international calling code, without "+"
    moeda: str  # ISO 4217, see apps/core/moedas.py
    fusos: tuple  # IANA time zones; the first is the default
    ingles: str  # language code of the English variant (dates and times)


PAISES = {
    "BR": Pais(
        _("Brasil"),
        "55",
        "BRL",
        (
            "America/Sao_Paulo",
            "America/Manaus",
            "America/Cuiaba",
            "America/Campo_Grande",
            "America/Porto_Velho",
            "America/Boa_Vista",
            "America/Rio_Branco",
            "America/Noronha",
        ),
        "en",
    ),
    "US": Pais(
        _("Estados Unidos"),
        "1",
        "USD",
        (
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Phoenix",
            "America/Los_Angeles",
            "America/Anchorage",
            "Pacific/Honolulu",
        ),
        "en",
    ),
    "GB": Pais(_("Reino Unido"), "44", "GBP", ("Europe/London",), "en-gb"),
    "CA": Pais(
        _("Canadá"),
        "1",
        "CAD",
        (
            "America/Toronto",
            "America/Vancouver",
            "America/Edmonton",
            "America/Winnipeg",
            "America/Regina",
            "America/Halifax",
            "America/St_Johns",
        ),
        "en-ca",
    ),
    "AU": Pais(
        _("Austrália"),
        "61",
        "AUD",
        (
            "Australia/Sydney",
            "Australia/Melbourne",
            "Australia/Brisbane",
            "Australia/Adelaide",
            "Australia/Darwin",
            "Australia/Perth",
            "Australia/Hobart",
        ),
        "en-au",
    ),
    "ZA": Pais(_("África do Sul"), "27", "ZAR", ("Africa/Johannesburg",), "en-za"),
}

ESCOLHAS = [(codigo, pais.nome) for codigo, pais in PAISES.items()]


def _cidade(fuso):
    return fuso.split("/")[-1].replace("_", " ")


# Grouped by country, named by the zone's city ("New York", "Sao Paulo").
ESCOLHAS_FUSO = [(pais.nome, [(f, _cidade(f)) for f in pais.fusos]) for pais in PAISES.values()]
FUSO_PADRAO = PAISES[PADRAO].fusos[0]


def pais_da_clinica(clinica=None):
    """Code of the clinic's country: the current clinic's when none is given, Brazil without
    one."""
    if clinica is None:
        from .isolamento import clinica_atual

        clinica = clinica_atual()
    return getattr(clinica, "pais", None) or PADRAO


def do_codigo(codigo):
    return PAISES.get(codigo or PADRAO, PAISES[PADRAO])


def variante_do_idioma(idioma, pais):
    """The English variant for the clinic's country ("en-gb"...), or None to keep `idioma`."""
    if idioma and idioma.split("-")[0] == "en":
        variante = do_codigo(pais).ingles
        return None if variante == idioma else variante
    return None


# Phones ------------------------------------------------------------------------------------
# Stored as the national number (no country code, no trunk 0), which fits the 11 characters
# of the existing fields: 10 digits in the United States, Canada and the United Kingdom,
# 9 in Australia and South Africa. Brazil keeps validadores.normalizar_telefone.

_TELEFONE = {
    # country: (digits of the national number, its first digit, message)
    "US": ((10,), "23456789", _("Informe o código de área e o número (10 dígitos).")),
    "CA": ((10,), "23456789", _("Informe o código de área e o número (10 dígitos).")),
    "GB": (
        (9, 10),
        "123578",
        _("Informe o número com o código de área (10 ou 11 dígitos com o 0)."),
    ),
    "AU": ((9,), "23478", _("Informe o número com o código de área (10 dígitos com o 0).")),
    "ZA": ((9,), "123456789", _("Informe o número com o código de área (10 dígitos com o 0).")),
}


def normalizar_telefone_internacional(digitos, pais):
    """National number of a phone outside Brazil from its digits, or ValidationError."""
    ddi = do_codigo(pais).ddi
    tamanhos, inicios, mensagem = _TELEFONE[pais]
    numero = digitos
    if numero.startswith("00"):  # international prefix typed
        numero = numero[2:]
    if numero.startswith(ddi) and len(numero) - len(ddi) in tamanhos:
        numero = numero[len(ddi) :]
    if pais not in ("US", "CA"):
        numero = numero.lstrip("0")  # trunk prefix
    if len(numero) not in tamanhos or numero[0] not in inicios:
        raise ValidationError(mensagem)
    return numero


def formatar_telefone(numero, pais):
    """A stored national number written the way the country writes it."""
    if not numero:
        return ""
    if pais in ("US", "CA") and len(numero) == 10:
        return f"({numero[:3]}) {numero[3:6]}-{numero[6:]}"
    if pais == "GB":
        if numero.startswith("2") and len(numero) == 10:  # London, Cardiff... 020 xxxx xxxx
            return f"0{numero[:2]} {numero[2:6]} {numero[6:]}"
        return f"0{numero[:4]} {numero[4:]}"
    if pais == "AU" and len(numero) == 9:
        if numero.startswith("4"):  # mobile 04xx xxx xxx
            return f"0{numero[:3]} {numero[3:6]} {numero[6:]}"
        return f"(0{numero[0]}) {numero[1:5]} {numero[5:]}"
    if pais == "ZA" and len(numero) == 9:
        return f"0{numero[:2]} {numero[2:5]} {numero[5:]}"
    return numero


def link_whatsapp(numero, pais):
    return f"https://wa.me/{do_codigo(pais).ddi}{numero}" if numero else ""


# Postal codes ------------------------------------------------------------------------------
# Stored without spaces or hyphens, letters in upper case (up to 9 characters: ZIP+4).

_CEP = {
    "BR": (r"\d{8}", _("O CEP deve ter 8 dígitos.")),
    "US": (r"\d{5}(\d{4})?", _("O ZIP code tem 5 dígitos (ou 9, com a extensão).")),
    "CA": (r"[A-Z]\d[A-Z]\d[A-Z]\d", _("O código postal canadense tem o formato A1A 1A1.")),
    "GB": (r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}", _("Informe um postcode válido, como SW1A 1AA.")),
    "AU": (r"\d{4}", _("O postcode australiano tem 4 dígitos.")),
    "ZA": (r"\d{4}", _("O código postal sul-africano tem 4 dígitos.")),
}


def normalizar_cep(valor, pais):
    cep = re.sub(r"[\s\-.]", "", valor or "").upper()
    if not cep:
        return ""
    padrao, mensagem = _CEP.get(pais, _CEP[PADRAO])
    if not re.fullmatch(padrao, cep):
        raise ValidationError(mensagem)
    return cep


def formatar_cep(cep, pais):
    if not cep:
        return ""
    if pais == "BR" and len(cep) == 8:
        return f"{cep[:5]}-{cep[5:]}"
    if pais == "US" and len(cep) == 9:
        return f"{cep[:5]}-{cep[5:]}"
    if pais in ("CA", "GB") and len(cep) > 3:
        return f"{cep[:-3]} {cep[-3:]}"
    return cep


def rotulo_cep(pais):
    """Field label: "CEP" in Brazil, a postal code anywhere else."""
    return _("CEP") if pais == "BR" else _("Código postal")
