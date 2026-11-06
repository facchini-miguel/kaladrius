from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import releases


@login_required
def whats_new_list(request):
    versions = releases.for_audience("equipe")
    modulos = sorted({(item.modulo, item.modulo_nome) for _, itens in versions for item in itens})
    modulo = request.GET.get("module", "")
    if modulo:
        versions = [
            (release, tuple(item for item in itens if item.modulo == modulo))
            for release, itens in versions
        ]
        versions = [(release, itens) for release, itens in versions if itens]

    # Opening this page clears the "new version" notice.
    current = releases.current_version()
    if request.user.last_seen_version != current:
        request.user.last_seen_version = current
        request.user.save(update_fields=["last_seen_version"])

    return render(
        request,
        "whats_new/list.html",
        {"versions": versions, "modules": modulos, "module": modulo},
    )
