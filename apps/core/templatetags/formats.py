"""Display formats of the clinic's country: documents, phone numbers and postal codes (stored
unformatted) and amounts in the clinic's currency."""

from django import template

from apps.core import countries, currencies, identification

register = template.Library()


@register.filter
def document(value, roles=""):
    """A document written the country's way: 123.456.789-09, 12-3456789, 943 476 5919. The
    roles ("patient", "company,person"; see apps/core/identification.py) say which documents
    it may be; all of the country's by default."""
    return identification.write(value, identification.roles(roles))


@register.filter
def document_abbreviation(value, roles=""):
    """The name of the document this value is ("CNPJ"), or every one the roles may have."""
    return identification.abbreviation(value, identification.roles(roles))


@register.simple_tag
def document_label(*roles):
    """The documents of these roles in the clinic's country: "CPF/CNPJ", "RUT", "EIN"."""
    return identification.for_country().label(*(roles or identification.DOCUMENT_ROLES))


@register.filter
def phone(value):
    value = value or ""
    country = countries.clinic_country()
    if country != "BR":
        return countries.format_phone(value, country)
    if len(value) == 11:
        return f"({value[:2]}) {value[2:7]}-{value[7:]}"
    if len(value) == 10:
        return f"({value[:2]}) {value[2:6]}-{value[6:]}"
    return value


@register.filter
def whatsapp(value):
    """Link that opens a WhatsApp chat: DDD and number in Brazil, the national number with the
    country code elsewhere (decision 117)."""
    value = value or ""
    country = countries.clinic_country()
    if country != "BR":
        return countries.whatsapp_link(value, country)
    return f"https://wa.me/55{value}" if len(value) in (10, 11) else ""


@register.filter
def postal_code(value):
    value = value or ""
    country = countries.clinic_country()
    if country != "BR":
        return countries.format_postal_code(value, country)
    if len(value) == 8:
        return f"{value[:5]}-{value[5:]}"
    return value


@register.filter
def currency(value):
    """Amount in the clinic's currency with the separators of the current language
    (R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €; see apps/core/currencies.py)."""
    return currencies.format_amount(value)


@register.simple_tag
def postal_code_label():
    """ "CEP" in Brazil, a postal code anywhere else (decision 117)."""
    return countries.postal_code_label(countries.clinic_country())


@register.simple_tag
def currency_symbol():
    """Symbol of the clinic's currency (R$, US$, €...), for labels and examples."""
    return currencies.symbol()
