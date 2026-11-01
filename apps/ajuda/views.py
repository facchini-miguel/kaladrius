from django.shortcuts import redirect, render

from apps.core import legislacao, paises
from apps.core.models import Clinica

from . import documentos


def para_o_site(request, pagina=None, caminho=None):
    """Old in-system help addresses (before 0.27.0) now open the documentation site."""
    if pagina == "privacidade":
        return redirect("privacidade")
    if pagina is not None:
        return redirect(documentos.url_do_site(f"manual/{pagina}"))
    if caminho is not None:
        return redirect(documentos.url_do_site())
    return redirect(documentos.url_do_site("manual/inicio"))


def privacidade(request):
    """Privacy policy (0.21.0, decision 055): public, since patients do not log in.

    The privacy contact is the clinic's: the user's clinic, or the installation's clinic
    for anyone else (one installation serves one clinic, decision 069).
    """
    clinica = getattr(request, "clinica", None) or Clinica.unica()
    titulo, html = documentos.privacidade()
    # The policy is written for Brazilian law: elsewhere, the country's law comes first.
    pais = paises.pais_da_clinica(clinica)
    contexto = {"titulo": titulo, "html": html, "clinica": clinica}
    if pais != paises.PADRAO:
        contexto.update(
            pais=paises.do_codigo(pais).nome,
            lei=legislacao.do_pais(pais),
            prazo_de_guarda=legislacao.prazo_de_guarda(pais),
        )
    return render(request, "ajuda/privacidade.html", contexto)
