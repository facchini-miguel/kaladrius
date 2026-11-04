"""The clinic's country (decisions 117 and 120): time zone, phones, postal codes, the English
and Spanish variants of dates and numbers, and the default currency. Brazil keeps every rule it
had; the other countries are the English-speaking markets (United States, United Kingdom,
Canada, Australia and South Africa) and Latin America (Mexico, Argentina, Chile, Colombia, Peru,
Uruguay, Paraguay, Bolivia and Ecuador). Each country's documents are in identification.py
(decision 121).
"""

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

PADRAO = "BR"


@dataclass(frozen=True)
class Pais:
    name: str
    ddi: str  # international calling code, without "+"
    currency: str  # ISO 4217, see apps/core/currencies.py
    fusos: tuple  # IANA time zones; the first is the default
    ingles: str = "en"  # language code of the English variant (dates and times)
    espanhol: str = "es"  # language code of the Spanish variant (dates and numbers)
    numeracao: str = "fdi"  # tooth numbering, see apps/dentistry/teeth.py (decision 122)


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
    # Latin America (decision 120): Spanish with each country's numbers (1,234.56 in Mexico
    # and Peru, 1.234,56 in the others) and dates.
    "MX": Pais(
        _("México"),
        "52",
        "MXN",
        (
            "America/Mexico_City",
            "America/Cancun",
            "America/Chihuahua",
            "America/Hermosillo",
            "America/Mazatlan",
            "America/Tijuana",
        ),
        espanhol="es-mx",
    ),
    "AR": Pais(
        _("Argentina"),
        "54",
        "ARS",
        (
            "America/Argentina/Buenos_Aires",
            "America/Argentina/Cordoba",
            "America/Argentina/Mendoza",
        ),
        espanhol="es-ar",
    ),
    "CL": Pais(
        _("Chile"),
        "56",
        "CLP",
        ("America/Santiago", "America/Punta_Arenas", "Pacific/Easter"),
        espanhol="es-cl",
    ),
    "CO": Pais(_("Colômbia"), "57", "COP", ("America/Bogota",), espanhol="es-co"),
    "PE": Pais(_("Peru"), "51", "PEN", ("America/Lima",), espanhol="es-pe"),
    "UY": Pais(_("Uruguai"), "598", "UYU", ("America/Montevideo",), espanhol="es-uy"),
    "PY": Pais(_("Paraguai"), "595", "PYG", ("America/Asuncion",), espanhol="es-py"),
    "BO": Pais(_("Bolívia"), "591", "BOB", ("America/La_Paz",), espanhol="es-bo"),
    "EC": Pais(
        _("Equador"), "593", "USD", ("America/Guayaquil", "Pacific/Galapagos"), espanhol="es-ec"
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
        numeracao="universal",
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

ESCOLHAS = [(code, country.name) for code, country in PAISES.items()]


def _cidade(fuso):
    return fuso.split("/")[-1].replace("_", " ")


# Grouped by country, named by the zone's city ("New York", "Sao Paulo").
ESCOLHAS_FUSO = [
    (country.name, [(f, _cidade(f)) for f in country.fusos]) for country in PAISES.values()
]
FUSO_PADRAO = PAISES[PADRAO].fusos[0]


def pais_da_clinica(clinic=None):
    """Code of the clinic's country: the current clinic's when none is given, Brazil without
    one."""
    if clinic is None:
        from .isolation import clinica_atual

        clinic = clinica_atual()
    return getattr(clinic, "country", None) or PADRAO


def do_codigo(code):
    return PAISES.get(code or PADRAO, PAISES[PADRAO])


def variante_do_idioma(language, country):
    """The English or Spanish variant for the clinic's country ("en-gb", "es-mx"...), or None
    to keep `idioma`. Portuguese has no variants."""
    base = (language or "").split("-")[0]
    variante = {"en": do_codigo(country).ingles, "es": do_codigo(country).espanhol}.get(base)
    return None if variante in (None, language) else variante


# Phones ------------------------------------------------------------------------------------
# Stored as the national number (no country code, no trunk 0), which fits the 11 characters
# of the existing fields: 8 to 10 digits. Brazil keeps validadores.normalizar_telefone.

_DEZ_DIGITOS = _("Informe o código de área e o número (10 dígitos).")
_TELEFONE = {
    "MX": ((10,), "23456789", _DEZ_DIGITOS),
    "AR": ((10,), "123", _DEZ_DIGITOS),
    "CL": ((9,), "2345679", _("Informe o número com o código de área (9 dígitos).")),
    "CO": ((10,), "36", _DEZ_DIGITOS),
    "PE": ((8, 9), "1456789", _("Informe o número com o código de área (8 ou 9 dígitos).")),
    "UY": ((8,), "249", _("Informe o número com o código de área (8 dígitos).")),
    "PY": ((8, 9), "2345679", _("Informe o número com o código de área (8 ou 9 dígitos).")),
    "BO": ((8,), "234567", _("Informe o número com o código de área (8 dígitos).")),
    "EC": ((8, 9), "2345679", _("Informe o número com o código de área (8 ou 9 dígitos).")),
    # country: (digits of the national number, its first digit, message)
    "US": ((10,), "23456789", _DEZ_DIGITOS),
    "CA": ((10,), "23456789", _DEZ_DIGITOS),
    "GB": (
        (9, 10),
        "123578",
        _("Informe o número com o código de área (10 ou 11 dígitos com o 0)."),
    ),
    "AU": ((9,), "23478", _("Informe o número com o código de área (10 dígitos com o 0).")),
    "ZA": ((9,), "123456789", _("Informe o número com o código de área (10 dígitos com o 0).")),
}


def normalizar_telefone_internacional(digitos, country):
    """National number of a phone outside Brazil from its digits, or ValidationError."""
    ddi = do_codigo(country).ddi
    tamanhos, inicios, mensagem = _TELEFONE[country]
    number = digitos
    if number.startswith("00"):  # international prefix typed
        number = number[2:]
    if country == "MX" and number.startswith("521") and len(number) == 13:
        number = number[3:]  # the old "1" of Mexican mobiles after +52
    elif country == "AR" and number.startswith("549") and len(number) == 13:
        number = number[3:]  # the "9" of Argentine mobiles after +54
    if number.startswith(ddi) and len(number) - len(ddi) in tamanhos:
        number = number[len(ddi) :]
    if country not in ("US", "CA"):
        number = number.lstrip("0")  # trunk prefix
    if country == "AR" and len(number) == 12:
        # Argentine mobiles are dialed with "15" after the area code (2 to 4 digits): it is
        # not part of the number.
        for area in (2, 3, 4):
            if number[area : area + 2] == "15":
                number = number[:area] + number[area + 2 :]
                break
    if len(number) not in tamanhos or number[0] not in inicios:
        raise ValidationError(mensagem)
    return number


def formatar_telefone(number, country):
    """A stored national number written the way the country writes it."""
    if not number:
        return ""
    if country in ("US", "CA") and len(number) == 10:
        return f"({number[:3]}) {number[3:6]}-{number[6:]}"
    if country == "GB":
        if number.startswith("2") and len(number) == 10:  # London, Cardiff... 020 xxxx xxxx
            return f"0{number[:2]} {number[2:6]} {number[6:]}"
        return f"0{number[:4]} {number[4:]}"
    if country == "AU" and len(number) == 9:
        if number.startswith("4"):  # mobile 04xx xxx xxx
            return f"0{number[:3]} {number[3:6]} {number[6:]}"
        return f"(0{number[0]}) {number[1:5]} {number[5:]}"
    if country == "ZA" and len(number) == 9:
        return f"0{number[:2]} {number[2:5]} {number[5:]}"
    return _formatar_telefone_latino(number, country)


def _formatar_telefone_latino(n, country):
    size = len(n)
    if country == "MX" and size == 10:
        if n[:2] in ("55", "33", "81"):  # Mexico City, Guadalajara, Monterrey: 2-digit areas
            return f"{n[:2]} {n[2:6]} {n[6:]}"
        return f"{n[:3]} {n[3:6]} {n[6:]}"
    if country == "AR" and size == 10:
        if n.startswith("11"):  # Buenos Aires
            return f"011 {n[2:6]}-{n[6:]}"
        return f"0{n[:3]} {n[3:6]}-{n[6:]}"
    if country == "CL" and size == 9:
        return f"{n[0]} {n[1:5]} {n[5:]}"
    if country == "CO" and size == 10:
        return f"{n[:3]} {n[3:6]} {n[6:]}"
    if country == "PE":
        if size == 9:
            return f"{n[:3]} {n[3:6]} {n[6:]}"
        if n.startswith("1"):  # Lima
            return f"(01) {n[1:4]} {n[4:]}"
        return f"(0{n[:2]}) {n[2:5]} {n[5:]}"
    if country == "UY" and size == 8:
        return f"0{n[:2]} {n[2:5]} {n[5:]}" if n.startswith("9") else f"{n[:4]} {n[4:]}"
    if country == "PY":
        if size == 9:
            return f"0{n[:3]} {n[3:6]} {n[6:]}"
        return f"(0{n[:2]}) {n[2:5]} {n[5:]}"
    if country == "BO" and size == 8:
        return f"{n[:4]} {n[4:]}"
    if country == "EC":
        if size == 9:
            return f"0{n[:2]} {n[2:5]} {n[5:]}"
        return f"(0{n[0]}) {n[1:4]} {n[4:]}"
    return n


def link_whatsapp(number, country):
    if not number:
        return ""
    # WhatsApp writes Argentine mobiles with a 9 after the country code.
    ddi = "549" if country == "AR" else do_codigo(country).ddi
    return f"https://wa.me/{ddi}{number}"


# Postal codes ------------------------------------------------------------------------------
# Stored without spaces or hyphens, letters in upper case (up to 9 characters: ZIP+4).

_CEP = {
    "BR": (r"\d{8}", _("O CEP deve ter 8 dígitos.")),
    "US": (r"\d{5}(\d{4})?", _("O ZIP code tem 5 dígitos (ou 9, com a extensão).")),
    "CA": (r"[A-Z]\d[A-Z]\d[A-Z]\d", _("O código postal canadense tem o formato A1A 1A1.")),
    "GB": (r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}", _("Informe um postcode válido, como SW1A 1AA.")),
    "AU": (r"\d{4}", _("O postcode australiano tem 4 dígitos.")),
    "ZA": (r"\d{4}", _("O código postal sul-africano tem 4 dígitos.")),
    "MX": (r"\d{5}", _("O código postal tem 5 dígitos.")),
    "AR": (
        r"[A-Z]\d{4}[A-Z]{3}|\d{4}",
        _("O código postal argentino tem o formato C1425ABC (ou 4 dígitos)."),
    ),
    "CL": (r"\d{7}", _("O código postal tem 7 dígitos.")),
    "CO": (r"\d{6}", _("O código postal tem 6 dígitos.")),
    "PE": (r"\d{5}", _("O código postal tem 5 dígitos.")),
    "UY": (r"\d{5}", _("O código postal tem 5 dígitos.")),
    "PY": (r"\d{4}(\d{2})?", _("O código postal tem 6 dígitos (ou 4, no formato antigo).")),
    # Bolivia has no national postal codes: whatever reference the address uses.
    "BO": (r"[A-Z0-9]{1,9}", _("Use até 9 letras ou números.")),
    "EC": (r"\d{6}", _("O código postal tem 6 dígitos.")),
}


def normalizar_cep(value, country):
    postal_code = re.sub(r"[\s\-.]", "", value or "").upper()
    if not postal_code:
        return ""
    padrao, mensagem = _CEP.get(country, _CEP[PADRAO])
    if not re.fullmatch(padrao, postal_code):
        raise ValidationError(mensagem)
    return postal_code


def formatar_cep(postal_code, country):
    if not postal_code:
        return ""
    if country == "BR" and len(postal_code) == 8:
        return f"{postal_code[:5]}-{postal_code[5:]}"
    if country == "US" and len(postal_code) == 9:
        return f"{postal_code[:5]}-{postal_code[5:]}"
    if country in ("CA", "GB") and len(postal_code) > 3:
        return f"{postal_code[:-3]} {postal_code[-3:]}"
    return postal_code


def rotulo_cep(country):
    """Field label: "CEP" in Brazil, a postal code anywhere else."""
    return _("CEP") if country == "BR" else _("Código postal")
