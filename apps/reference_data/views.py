from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.ordering import chave_alfabetica
from apps.core.permissions import Acao, Modulo, exige_permissao

from .models import Bank, City, Neighborhood, State, Street

POR_PAGINA = 50


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def cidades(request):
    ufs = State.objects.all()
    state = request.GET.get("state", "")
    busca = request.GET.get("q", "").strip()
    cidades = City.objects.select_related("state")
    if state.isdecimal():
        cidades = cidades.filter(state_id=int(state))
    if busca:
        cidades = cidades.filter(name__unaccent__icontains=busca)
    pagina = Paginator(cidades, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "reference_data/cities.html",
        {
            "ufs": ufs,
            "state": state,
            "busca": busca,
            "pagina": pagina,
            "parametros": urlencode({"state": state, "q": busca}),
        },
    )


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def bancos(request):
    busca = request.GET.get("q", "").strip()
    bancos = Bank.objects.all()
    if busca:
        filtro = Q(name__unaccent__icontains=busca) | Q(nome_curto__unaccent__icontains=busca)
        if busca.isdecimal():
            filtro |= Q(code=int(busca))
        bancos = bancos.filter(filtro)
    pagina = Paginator(bancos, POR_PAGINA).get_page(request.GET.get("pagina"))
    contexto = {"busca": busca, "pagina": pagina, "parametros": urlencode({"q": busca})}
    return render(request, "reference_data/banks.html", contexto)


@login_required
def opcoes_cidades(request):
    """<option> list of a state's cities, for chained UF → city selects (HTMX)."""
    state = request.GET.get("state", "")
    cidades = City.objects.filter(state_id=int(state)) if state.isdecimal() else City.objects.none()
    return render(request, "reference_data/city_options.html", {"cidades": cidades})


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def sugestoes_endereco(request):
    """<datalist>s of a city's neighborhoods and streets for the patient form (decision 100):
    the known ones plus the ones the clinic already typed for other patients there."""
    from apps.patients.models import Patient

    code = request.GET.get("city", "")
    bairros, logradouros = set(), set()
    if code.isdecimal():
        city = int(code)
        bairros.update(Neighborhood.objects.filter(city_id=city).values_list("name", flat=True))
        logradouros.update(Street.objects.filter(city_id=city).values_list("name", flat=True))
        da_clinica = Patient.objects.filter(city_id=city).values_list("neighborhood", "street")
        for neighborhood, street in da_clinica.distinct():
            bairros.add(neighborhood)
            logradouros.add(street)
    return render(
        request,
        "reference_data/address_suggestions.html",
        {
            "bairros": sorted(filter(None, bairros), key=chave_alfabetica),
            "logradouros": sorted(filter(None, logradouros), key=chave_alfabetica),
        },
    )
