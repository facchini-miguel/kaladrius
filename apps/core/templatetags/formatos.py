"""Display formats: Brazilian documents and phone numbers (stored unformatted) and amounts
in the clinic's currency."""

from django import template

from apps.core import moedas

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
def whatsapp(valor):
    """Link that opens a WhatsApp chat with a Brazilian number (DDD and number)."""
    valor = valor or ""
    return f"https://wa.me/55{valor}" if len(valor) in (10, 11) else ""


@register.filter
def cep(valor):
    valor = valor or ""
    if len(valor) == 8:
        return f"{valor[:5]}-{valor[5:]}"
    return valor


@register.filter
def moeda(valor):
    """Amount in the clinic's currency with the separators of the current language
    (R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €; see apps/core/moedas.py)."""
    return moedas.formatar(valor)


@register.simple_tag
def simbolo_moeda():
    """Symbol of the clinic's currency (R$, US$, €...), for labels and examples."""
    return moedas.simbolo()
