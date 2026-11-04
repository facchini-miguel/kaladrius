from django.utils.functional import SimpleLazyObject

from . import documents


def documentacao(request):
    """Links of the Help menu to the documentation site, in the current language."""
    return {
        "url_documentacao": SimpleLazyObject(documents.url_do_site),
        "url_manual": SimpleLazyObject(lambda: documents.url_do_site("manual/getting-started")),
    }
