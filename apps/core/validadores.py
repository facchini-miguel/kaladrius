import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

validar_cor = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use uma cor no formato #RRGGBB.")


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def normalizar_cnpj(valor):
    """Strip punctuation and uppercase. CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()


def cpf_valido(cpf):
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        if (soma * 10 % 11) % 10 != int(cpf[posicao]):
            return False
    return True


def cnpj_valido(cnpj):
    """Validate numeric and alphanumeric CNPJs (Receita Federal, IN RFB 2.229/2024).

    The first 12 characters may be digits or letters; each one is worth its ASCII
    code minus 48. The two check digits are always numeric.
    """
    cnpj = normalizar_cnpj(cnpj)
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj) or cnpj == cnpj[0] * 14:
        return False
    valores = [ord(caractere) - 48 for caractere in cnpj]
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for posicao, pesos_da_vez in ((12, pesos), (13, [6, *pesos])):
        resto = sum(v * p for v, p in zip(valores[:posicao], pesos_da_vez, strict=True)) % 11
        if (0 if resto < 2 else 11 - resto) != valores[posicao]:
            return False
    return True


def validar_cpf(valor):
    if not cpf_valido(valor):
        raise ValidationError(_("CPF inválido."))


def validar_cnpj(valor):
    if not cnpj_valido(valor):
        raise ValidationError(_("CNPJ inválido."))


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


def nono_digito(numero):
    """An 8-digit mobile (DDD + number starting with 6 to 9) with the ninth digit added."""
    if len(numero) == 10 and numero[2] in "6789":
        return f"{numero[:2]}9{numero[2:]}"
    return numero


def normalizar_telefone(valor):
    """A Brazilian phone as DDD + number digits, or ValidationError.

    Accepts what people type: punctuation, a leading 0 (carrier prefix) or +55. A mobile
    written the old way, with 8 digits starting with 6 to 9, gets the ninth digit (Anatel's
    rule: landlines start with 2 to 5), so WhatsApp links work.
    """
    numero = somente_digitos(valor).lstrip("0")
    if len(numero) in (12, 13) and numero.startswith("55"):
        numero = numero[2:]
    if not numero:
        return ""
    if len(numero) not in (10, 11):
        raise ValidationError(_("Informe o DDD e o número (10 ou 11 dígitos)."))
    if int(numero[:2]) not in DDDS:
        raise ValidationError(_("O DDD %(ddd)s não existe.") % {"ddd": numero[:2]})
    if len(numero) == 11 and numero[2] != "9":
        raise ValidationError(_("Com 11 dígitos, o número começa com 9 depois do DDD."))
    return nono_digito(numero)
