"""Display formats of the clinic's country: documents, phone numbers and postal codes (stored
unformatted) and amounts in the clinic's currency."""

from django import template

from apps.core import identificacao, moedas, paises

register = template.Library()


@register.filter
def documento(valor, papeis=""):
    """A document written the country's way: 123.456.789-09, 12-3456789, 943 476 5919. The
    roles ("paciente", "empresa,pessoa"; see apps/core/identificacao.py) say which documents
    it may be; all of the country's by default."""
    return identificacao.escrever(valor, identificacao.papeis(papeis))


@register.filter
def sigla_documento(valor, papeis=""):
    """The name of the document this value is ("CNPJ"), or every one the roles may have."""
    return identificacao.sigla(valor, identificacao.papeis(papeis))


@register.simple_tag
def rotulo_documento(*papeis):
    """The documents of these roles in the clinic's country: "CPF/CNPJ", "RUT", "EIN"."""
    return identificacao.do_pais().rotulo(*(papeis or identificacao.PAPEIS))


@register.filter
def telefone(valor):
    valor = valor or ""
    pais = paises.pais_da_clinica()
    if pais != "BR":
        return paises.formatar_telefone(valor, pais)
    if len(valor) == 11:
        return f"({valor[:2]}) {valor[2:7]}-{valor[7:]}"
    if len(valor) == 10:
        return f"({valor[:2]}) {valor[2:6]}-{valor[6:]}"
    return valor


@register.filter
def whatsapp(valor):
    """Link that opens a WhatsApp chat: DDD and number in Brazil, the national number with the
    country code elsewhere (decision 117)."""
    valor = valor or ""
    pais = paises.pais_da_clinica()
    if pais != "BR":
        return paises.link_whatsapp(valor, pais)
    return f"https://wa.me/55{valor}" if len(valor) in (10, 11) else ""


@register.filter
def cep(valor):
    valor = valor or ""
    pais = paises.pais_da_clinica()
    if pais != "BR":
        return paises.formatar_cep(valor, pais)
    if len(valor) == 8:
        return f"{valor[:5]}-{valor[5:]}"
    return valor


@register.filter
def moeda(valor):
    """Amount in the clinic's currency with the separators of the current language
    (R$ 1.234,56 · US$ 1,234.56 · 1.234,56 €; see apps/core/moedas.py)."""
    return moedas.formatar(valor)


@register.simple_tag
def rotulo_cep():
    """ "CEP" in Brazil, a postal code anywhere else (decision 117)."""
    return paises.rotulo_cep(paises.pais_da_clinica())


@register.simple_tag
def simbolo_moeda():
    """Symbol of the clinic's currency (R$, US$, €...), for labels and examples."""
    return moedas.simbolo()
