import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from . import countries

validate_color = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use uma cor no formato #RRGGBB.")


def digits_only(value):
    return re.sub(r"\D", "", value or "")


def normalize_cnpj(value):
    """Strip punctuation and uppercase. CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def valid_cpf(cpf):
    cpf = digits_only(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for position in (9, 10):
        weighted_sum = sum(int(cpf[i]) * (position + 1 - i) for i in range(position))
        if (weighted_sum * 10 % 11) % 10 != int(cpf[position]):
            return False
    return True


def valid_cnpj(cnpj):
    """Validate numeric and alphanumeric CNPJs (Receita Federal, IN RFB 2.229/2024).

    The first 12 characters may be digits or letters; each one is worth its ASCII
    code minus 48. The two check digits are always numeric.
    """
    cnpj = normalize_cnpj(cnpj)
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj) or cnpj == cnpj[0] * 14:
        return False
    values = [ord(character) - 48 for character in cnpj]
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for position, weights in ((12, pesos), (13, [6, *pesos])):
        remainder = sum(v * p for v, p in zip(values[:position], weights, strict=True)) % 11
        if (0 if remainder < 2 else 11 - remainder) != values[position]:
            return False
    return True


def validate_cpf(value):
    if not valid_cpf(value):
        raise ValidationError(_("Invalid CPF."))


def validate_cnpj(value):
    if not valid_cnpj(value):
        raise ValidationError(_("Invalid CNPJ."))


# Brazilian area codes (DDD) in use, from Anatel's numbering plan.
DDDS = {
    *range(11, 20),
    21,
    22,
    24,
    27,
    28,
    *range(31, 36),
    37,
    38,
    *range(41, 50),
    51,
    53,
    54,
    55,
    *range(61, 70),
    71,
    73,
    74,
    75,
    77,
    79,
    *range(81, 90),
    *range(91, 100),
}


def ninth_digit(number):
    """An 8-digit mobile (DDD + number starting with 6 to 9) with the ninth digit added."""
    if len(number) == 10 and number[2] in "6789":
        return f"{number[:2]}9{number[2:]}"
    return number


def normalize_phone(value, country=None):
    """A phone of the clinic's country as stored digits, or ValidationError.

    Brazil: DDD + number. Accepts what people type: punctuation, a leading 0 (carrier prefix)
    or +55. A mobile written the old way, with 8 digits starting with 6 to 9, gets the ninth
    digit (Anatel's rule: landlines start with 2 to 5), so WhatsApp links work. Other countries
    (decision 117): the national number, see countries.normalizar_telefone_internacional.
    """
    country = country or countries.clinic_country()
    if country != "BR":
        digits = digits_only(value)
        return countries.normalize_international_phone(digits, country) if digits else ""
    number = digits_only(value).lstrip("0")
    if len(number) in (12, 13) and number.startswith("55"):
        number = number[2:]
    if not number:
        return ""
    if len(number) not in (10, 11):
        raise ValidationError(_("Enter the area code and number (10 or 11 digits)."))
    if int(number[:2]) not in DDDS:
        raise ValidationError(
            _("Area code %(area_code)s does not exist.") % {"area_code": number[:2]}
        )
    if len(number) == 11 and number[2] != "9":
        raise ValidationError(_("With 11 digits, the number starts with 9 after the area code."))
    return ninth_digit(number)
