from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.ordering import alphabetical_key
from apps.core.permissions import Action, Module, requires_permission

from .models import Bank, City, Neighborhood, State, Street

PER_PAGE = 50


@requires_permission(Module.CATALOGS, Action.VIEW)
def cities(request):
    ufs = State.objects.all()
    state = request.GET.get("state", "")
    search = request.GET.get("q", "").strip()
    cities = City.objects.select_related("state")
    if state.isdecimal():
        cities = cities.filter(state_id=int(state))
    if search:
        cities = cities.filter(name__unaccent__icontains=search)
    page = Paginator(cities, PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "reference_data/cities.html",
        {
            "states": ufs,
            "state": state,
            "search": search,
            "page": page,
            "query": urlencode({"state": state, "q": search}),
        },
    )


@requires_permission(Module.CATALOGS, Action.VIEW)
def banks(request):
    search = request.GET.get("q", "").strip()
    banks = Bank.objects.all()
    if search:
        filtro = Q(name__unaccent__icontains=search) | Q(short_name__unaccent__icontains=search)
        if search.isdecimal():
            filtro |= Q(code=int(search))
        banks = banks.filter(filtro)
    page = Paginator(banks, PER_PAGE).get_page(request.GET.get("page"))
    context = {"search": search, "page": page, "query": urlencode({"q": search})}
    return render(request, "reference_data/banks.html", context)


@login_required
def city_options(request):
    """<option> list of a state's cities, for chained UF → city selects (HTMX)."""
    state = request.GET.get("state", "")
    cities = City.objects.filter(state_id=int(state)) if state.isdecimal() else City.objects.none()
    return render(request, "reference_data/city_options.html", {"cities": cities})


@requires_permission(Module.PATIENTS, Action.VIEW)
def address_suggestions(request):
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
            "neighborhoods": sorted(filter(None, bairros), key=alphabetical_key),
            "streets": sorted(filter(None, logradouros), key=alphabetical_key),
        },
    )
