"""The teeth in the clinic's numbering (decision 122); stored and posted in FDI."""

from django import template

from apps.odontologia import dentes

register = template.Library()


@register.filter
def nome_dente(dente):
    return dentes.nome(dente)


@register.simple_tag
def legenda_numeracao():
    return dentes.LEGENDAS[dentes.numeracao_da_clinica()]
