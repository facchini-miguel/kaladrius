from django.shortcuts import redirect, render

from apps.core import countries, legislation
from apps.core.models import Clinic

from . import documents

# The user manual's pages, by the names the in-system help used (before 0.27.0) and the site
# used until decision 151.
PAGINAS = {
    "inicio": "getting-started",
    "agenda": "schedule",
    "clinica": "clinic",
    "convenios": "health-plans",
    "equipe": "team",
    "financeiro": "finance",
    "orcamentos": "estimates",
    "pacientes": "patients",
    "pessoal": "staff",
    "prontuario": "medical-record",
    "rechamadas": "recalls",
}


def para_o_site(request, page=None, path=None):
    """Old in-system help addresses (before 0.27.0) now open the documentation site."""
    if page in ("privacidade", "privacy"):
        return redirect("privacy")
    if page is not None:
        return redirect(documents.url_do_site(f"manual/{PAGINAS.get(page, page)}"))
    if path is not None:
        return redirect(documents.url_do_site())
    return redirect(documents.url_do_site("manual/getting-started"))


def privacidade(request):
    """Privacy policy (0.21.0, decision 055): public, since patients do not log in.

    The privacy contact is the clinic's: the user's clinic, or the installation's clinic
    for anyone else (one installation serves one clinic, decision 069).
    """
    clinic = getattr(request, "clinic", None) or Clinic.unica()
    titulo, html = documents.privacidade()
    # The policy is written for Brazilian law: elsewhere, the country's law comes first.
    country = countries.pais_da_clinica(clinic)
    context = {"titulo": titulo, "html": html, "clinic": clinic}
    if country != countries.PADRAO:
        context.update(
            country=countries.do_codigo(country).name,
            lei=legislation.do_pais(country),
            prazo_de_guarda=legislation.prazo_de_guarda(country),
        )
    return render(request, "help/privacy.html", context)
