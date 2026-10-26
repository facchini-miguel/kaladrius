"""Display formats for Brazilian documents and phone numbers (values are stored unformatted)."""

from django import template

register = template.Library()


@register.filter
def cpf_cnpj(valor):
    valor = valor or ""
    if len(valor) == 11:
        return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
    if len(valor) == 14:
        return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
    return valor


@register.filter
def telefone(valor):
    valor = valor or ""
    if len(valor) == 11:
        return f"({valor[:2]}) {valor[2:7]}-{valor[7:]}"
    if len(valor) == 10:
        return f"({valor[:2]}) {valor[2:6]}-{valor[6:]}"
    return valor


@register.filter
def cep(valor):
    valor = valor or ""
    if len(valor) == 8:
        return f"{valor[:5]}-{valor[5:]}"
    return valor
