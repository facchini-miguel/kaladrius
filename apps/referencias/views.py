from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .models import UF, Bairro, Banco, Cidade, Logradouro

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


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def sugestoes_endereco(request):
    """<datalist>s of a city's neighborhoods and streets for the patient form (decision 100):
    the known ones plus the ones the clinic already typed for other patients there."""
    from apps.pacientes.models import Paciente

    codigo = request.GET.get("cidade", "")
    bairros, logradouros = set(), set()
    if codigo.isdecimal():
        cidade = int(codigo)
        bairros.update(Bairro.objects.filter(cidade_id=cidade).values_list("nome", flat=True))
        logradouros.update(
            Logradouro.objects.filter(cidade_id=cidade).values_list("nome", flat=True)
        )
        da_clinica = Paciente.objects.filter(cidade_id=cidade).values_list("bairro", "logradouro")
        for bairro, logradouro in da_clinica.distinct():
            bairros.add(bairro)
            logradouros.add(logradouro)
    return render(
        request,
        "referencias/sugestoes_endereco.html",
        {
            "bairros": sorted(filter(None, bairros), key=str.casefold),
            "logradouros": sorted(filter(None, logradouros), key=str.casefold),
        },
    )
