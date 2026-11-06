from django.conf import settings

from . import releases


def version_context(request):
    context = {"system_version": releases.current_version(), "system_name": settings.SYSTEM_NAME}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        context["new_version"] = releases.has_news_for(user.last_seen_version)
    return context
