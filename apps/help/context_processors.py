from django.utils.functional import SimpleLazyObject

from . import documents


def documentation(request):
    """Links of the Help menu to the documentation site, in the current language."""
    return {
        "docs_url": SimpleLazyObject(documents.site_url),
        "manual_url": SimpleLazyObject(lambda: documents.site_url("manual/getting-started")),
    }
