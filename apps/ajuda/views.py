from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from apps.core.models import Clinica

from . import documentos


@login_required
def indice(request):
    return redirect("ajuda:manual", pagina=documentos.MANUAL[0])


@login_required
def manual(request, pagina):
    if pagina == "privacidade":
        return redirect("privacidade")  # the public page, with the clinic's contact
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


def privacidade(request):
    """Privacy policy (0.21.0, decision 055): public, since patients do not log in.

    The privacy contact is the clinic's: the current one for a logged-in user, or the
    only active clinic when there is just one (otherwise the page asks to contact the
    clinic that treats you).
    """
    clinica = getattr(request, "clinica", None)
    if clinica is None:
        ativas = list(Clinica.objects.filter(ativa=True)[:2])
        clinica = ativas[0] if len(ativas) == 1 else None
    titulo, html = documentos.manual("privacidade")
    return render(
        request, "ajuda/privacidade.html", {"titulo": titulo, "html": html, "clinica": clinica}
    )
