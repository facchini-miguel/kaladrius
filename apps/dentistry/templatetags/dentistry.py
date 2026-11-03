"""The teeth in the clinic's numbering (decision 122); stored and posted in FDI."""

from django import template

from apps.dentistry import teeth

register = template.Library()


@register.filter
def nome_dente(dente):
    return teeth.nome(dente)


@register.simple_tag
def legenda_numeracao():
    return teeth.LEGENDAS[teeth.numeracao_da_clinica()]
