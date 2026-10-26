from django.utils.functional import SimpleLazyObject

from .middleware import clinicas_do_usuario
from .permissoes import tabela_permissoes


def clinica(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {
        "clinica_atual": getattr(request, "clinica", None),
        "vinculo_atual": getattr(request, "vinculo", None),
        "pode": SimpleLazyObject(lambda: tabela_permissoes(request)),
        "clinicas_do_usuario": SimpleLazyObject(lambda: list(clinicas_do_usuario(usuario))),
    }
