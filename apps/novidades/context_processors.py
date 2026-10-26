from . import releases


def versao(request):
    contexto = {"versao_sistema": releases.versao_atual()}
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        contexto["versao_nova"] = releases.tem_novidade_para(usuario.ultima_versao_vista)
    return contexto
