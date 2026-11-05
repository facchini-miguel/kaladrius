from django.utils.functional import SimpleLazyObject

from . import documents


def documentation(request):
    """Links of the Help menu to the documentation site, in the current language."""
    return {
        "url_documentacao": SimpleLazyObject(documents.site_url),
        "url_manual": SimpleLazyObject(lambda: documents.site_url("manual/getting-started")),
    }
