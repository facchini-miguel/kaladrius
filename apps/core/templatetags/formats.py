"""Display formats of the clinic's country: documents, phone numbers and postal codes (stored
unformatted) and amounts in the clinic's currency."""

from django import template

from apps.core import countries, currencies, identification

register = template.Library()


@register.filter
def documento(value, papeis=""):
    """A document written the country's way: 123.456.789-09, 12-3456789, 943 476 5919. The
    roles ("paciente", "empresa,pessoa"; see apps/core/identification.py) say which documents
    it may be; all of the country's by default."""
    return identification.escrever(value, identification.papeis(papeis))


@register.filter
def sigla_documento(value, papeis=""):
    """The name of the document this value is ("CNPJ"), or every one the roles may have."""
    return identification.sigla(value, identification.papeis(papeis))


@register.simple_tag
def rotulo_documento(*papeis):
    """The documents of these roles in the clinic's country: "CPF/CNPJ", "RUT", "EIN"."""
    return identification.do_pais().rotulo(*(papeis or identification.PAPEIS))


@register.filter
def phone(value):
    value = value or ""
    pais = countries.pais_da_clinica()
    if pais != "BR":
        return countries.formatar_telefone(value, pais)
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
    pais = countries.pais_da_clinica()
    if pais != "BR":
        return countries.link_whatsapp(value, pais)
    return f"https://wa.me/55{value}" if len(value) in (10, 11) else ""


@register.filter
def cep(value):
    value = value or ""
    pais = countries.pais_da_clinica()
    if pais != "BR":
        return countries.formatar_cep(value, pais)
    if len(value) == 8:
        return f"{value[:5]}-{value[5:]}"
    return value


@register.filter
def moeda(value):
    """Amount in the clinic's currency with the separators of the current language
    (R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €; see apps/core/currencies.py)."""
    return currencies.formatar(value)


@register.simple_tag
def rotulo_cep():
    """ "CEP" in Brazil, a postal code anywhere else (decision 117)."""
    return countries.rotulo_cep(countries.pais_da_clinica())


@register.simple_tag
def simbolo_moeda():
    """Symbol of the clinic's currency (R$, US$, €...), for labels and examples."""
    return currencies.simbolo()
