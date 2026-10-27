from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .models import UF, Banco, Cidade

POR_PAGINA = 50


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def cidades(request):
    ufs = UF.objects.all()
    uf = request.GET.get("uf", "")
    busca = request.GET.get("q", "").strip()
    cidades = Cidade.objects.select_related("uf")
    if uf.isdecimal():
        cidades = cidades.filter(uf_id=int(uf))
    if busca:
        cidades = cidades.filter(nome__unaccent__icontains=busca)
    pagina = Paginator(cidades, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "referencias/cidades.html",
        {
            "ufs": ufs,
            "uf": uf,
            "busca": busca,
            "pagina": pagina,
            "parametros": urlencode({"uf": uf, "q": busca}),
        },
    )


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def bancos(request):
    busca = request.GET.get("q", "").strip()
    bancos = Banco.objects.all()
    if busca:
        filtro = Q(nome__unaccent__icontains=busca) | Q(nome_curto__unaccent__icontains=busca)
        if busca.isdecimal():
            filtro |= Q(codigo=int(busca))
        bancos = bancos.filter(filtro)
    pagina = Paginator(bancos, POR_PAGINA).get_page(request.GET.get("pagina"))
    contexto = {"busca": busca, "pagina": pagina, "parametros": urlencode({"q": busca})}
    return render(request, "referencias/bancos.html", contexto)


@login_required
def opcoes_cidades(request):
    """<option> list of a state's cities, for chained UF → city selects (HTMX)."""
    uf = request.GET.get("uf", "")
    cidades = Cidade.objects.filter(uf_id=int(uf)) if uf.isdecimal() else Cidade.objects.none()
    return render(request, "referencias/opcoes_cidades.html", {"cidades": cidades})
