from django.conf import settings

from . import releases


def version_context(request):
    context = {"versao_sistema": releases.current_version(), "nome_sistema": settings.SYSTEM_NAME}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        context["versao_nova"] = releases.has_news_for(user.last_seen_version)
    return context
