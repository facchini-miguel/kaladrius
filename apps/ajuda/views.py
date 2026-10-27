from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from . import documentos


@login_required
def indice(request):
    return redirect("ajuda:manual", pagina=documentos.MANUAL[0])


@login_required
def manual(request, pagina):
    try:
        titulo, html = documentos.manual(pagina)
    except documentos.DocumentoNaoEncontrado as erro:
        raise Http404 from erro
    return render(
        request,
        "ajuda/manual.html",
        {
            "titulo": titulo,
            "html": html,
            "pagina": pagina,
            "paginas": documentos.indice_do_manual(),
        },
    )


@login_required
def tecnica(request, caminho=None):
    """Technical documentation: superusers only (it describes the infrastructure).

    Other users get "not found", so the pages do not even reveal they exist.
    """
    if not request.user.is_superuser:
        raise Http404
    if caminho is None:
        return redirect("ajuda:tecnica", caminho=f"{documentos.pasta_do_idioma()}/README.md")
    try:
        titulo, html = documentos.renderizar(caminho, tecnica=True)
    except documentos.DocumentoNaoEncontrado as erro:
        raise Http404 from erro
    return render(
        request, "ajuda/tecnica.html", {"titulo": titulo, "html": html, "caminho": caminho}
    )
