"""The teeth in the clinic's numbering (decision 122); stored and posted in FDI."""

from django import template

from apps.dentistry import teeth

register = template.Library()


@register.filter
def tooth_name(tooth):
    return teeth.name(tooth)


@register.simple_tag
def numbering_legend():
    return teeth.LEGENDS[teeth.clinic_numbering()]
