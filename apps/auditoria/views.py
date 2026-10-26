import datetime

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .models import RegistroAuditoria

POR_PAGINA = 100


def _data(valor):
    try:
        return datetime.date.fromisoformat(valor or "")
    except ValueError:
        return None


@exige_permissao(Modulo.AUDITORIA, Acao.VER)
def lista(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    registros = RegistroAuditoria.objects.filter(clinica=request.clinica)
    filtros = {
        "q": request.GET.get("q", "").strip(),
        "acao": request.GET.get("acao", ""),
        "modelo": request.GET.get("modelo", ""),
        "de": request.GET.get("de", ""),
        "ate": request.GET.get("ate", ""),
    }
    modelos = sorted(set(registros.exclude(modelo="").values_list("modelo", flat=True)))
    if filtros["q"]:
        registros = registros.filter(
            Q(usuario_nome__icontains=filtros["q"])
            | Q(objeto_descricao__icontains=filtros["q"])
            | Q(objeto_id=filtros["q"])
        )
    if filtros["acao"] in RegistroAuditoria.Acao.values:
        registros = registros.filter(acao=filtros["acao"])
    if filtros["modelo"]:
        registros = registros.filter(modelo=filtros["modelo"])
    if de := _data(filtros["de"]):
        registros = registros.filter(momento__date__gte=de)
    if ate := _data(filtros["ate"]):
        registros = registros.filter(momento__date__lte=ate)
    pagina = Paginator(registros, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "auditoria/lista.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "parametros": urlencode(filtros),
            "acoes": RegistroAuditoria.Acao.choices,
            "modelos": modelos,
        },
    )
