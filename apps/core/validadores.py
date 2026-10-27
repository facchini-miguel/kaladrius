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
