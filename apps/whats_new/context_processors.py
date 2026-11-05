from django.conf import settings

from . import releases


def versao(request):
    contexto = {"versao_sistema": releases.versao_atual(), "nome_sistema": settings.NOME_SISTEMA}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        contexto["versao_nova"] = releases.tem_novidade_para(user.last_seen_version)
    return contexto
