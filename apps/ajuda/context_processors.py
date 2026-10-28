from django.utils.functional import SimpleLazyObject

from . import documentos


def documentacao(request):
    """Links of the Help menu to the documentation site, in the current language."""
    return {
        "url_documentacao": SimpleLazyObject(documentos.url_do_site),
        "url_manual": SimpleLazyObject(lambda: documentos.url_do_site("manual/inicio")),
    }
