from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import releases


@login_required
def lista(request):
    versoes = releases.para_publico("equipe")
    modulos = sorted({item.modulo for _, itens in versoes for item in itens})
    modulo = request.GET.get("modulo", "")
    if modulo:
        versoes = [
            (release, tuple(item for item in itens if item.modulo == modulo))
            for release, itens in versoes
        ]
        versoes = [(release, itens) for release, itens in versoes if itens]

    # Opening this page clears the "new version" notice.
    atual = releases.versao_atual()
    if request.user.ultima_versao_vista != atual:
        request.user.ultima_versao_vista = atual
        request.user.save(update_fields=["ultima_versao_vista"])

    return render(
        request,
        "novidades/lista.html",
        {"versoes": versoes, "modulos": modulos, "modulo": modulo},
    )
