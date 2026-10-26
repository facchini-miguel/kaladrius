from . import releases


def versao(request):
    return {"versao_sistema": releases.versao_atual()}
