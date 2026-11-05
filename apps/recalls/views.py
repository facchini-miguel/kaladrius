import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.permissions import Action, Module, requires_permission

from .forms import RecallForm
from .models import Recall

PER_PAGE = 50
STATUSES = {"pendentes": {"done": False}, "concluidas": {"done": True}, "todas": {}}


def _date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def _back(request, default="recalls:list"):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(default)


@requires_permission(Module.RECALLS, Action.VIEW)
def recall_list(request):
    status = request.GET.get("status", "pendentes")
    search = request.GET.get("q", "").strip()
    since, until = _date(request.GET.get("de")), _date(request.GET.get("until"))
    rechamadas = Recall.objects.select_related("patient").filter(
        **STATUSES.get(status, STATUSES["pendentes"]), patient__archived=False
    )
    if search:
        rechamadas = rechamadas.filter(patient__name__unaccent__icontains=search)
    if since:
        rechamadas = rechamadas.filter(date__gte=since)
    if until:
        rechamadas = rechamadas.filter(date__lte=until)
    page = Paginator(rechamadas, PER_PAGE).get_page(request.GET.get("pagina"))
    filters = {
        "q": search,
        "status": status,
        "de": since.isoformat() if since else "",
        "until": until.isoformat() if until else "",
    }
    return render(
        request,
        "recalls/list.html",
        {
            "pagina": page,
            "filtros": filters,
            "parametros": urlencode(filters),
            "hoje": timezone.localdate(),
        },
    )


@requires_permission(Module.RECALLS, Action.CREATE)
def new_recall(request):
    inicial = {"date": request.GET.get("date") or ""}
    if request.GET.get("patient", "").isdecimal():
        inicial["patient"] = request.GET["patient"]
    return _recall_form(request, Recall(created_by=request.user), inicial)


@requires_permission(Module.RECALLS, Action.CHANGE)
def edit_recall(request, pk):
    return _recall_form(request, get_object_or_404(Recall.objects, pk=pk), {})


def _recall_form(request, rechamada, inicial):
    form = RecallForm(
        request.POST or None, instance=rechamada, initial=inicial, clinic=request.clinic
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Rechamada de %(nome)s salva.") % {"nome": rechamada.patient.name}
        )
        return _back(request)
    patient = rechamada.patient if rechamada.patient_id else form["patient"].value()
    if patient and not hasattr(patient, "name"):
        # Raw value from the hidden field: may be anything when the request is tampered with.
        code = str(patient)
        consulta = form.fields["patient"].queryset
        patient = consulta.filter(pk=int(code)).first() if code.isdecimal() else None
    return render(
        request,
        "recalls/form.html",
        {
            "form": form,
            "rechamada": rechamada,
            "patient": patient,
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
@requires_permission(Module.RECALLS, Action.CHANGE)
def complete(request, pk):
    rechamada = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    rechamada.done = not rechamada.done
    rechamada.save(update_fields=["done", "updated_at"])
    if rechamada.done:
        message = _("Rechamada de %(nome)s concluída.")
    else:
        message = _("Rechamada de %(nome)s reaberta.")
    messages.success(request, message % {"nome": rechamada.patient.name})
    return _back(request)


@requires_permission(Module.RECALLS, Action.DELETE)
def delete_recall(request, pk):
    rechamada = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    if request.method == "POST":
        rechamada.delete()
        messages.success(
            request, _("Rechamada de %(nome)s excluída.") % {"nome": rechamada.patient.name}
        )
        return _back(request)
    return render(request, "recalls/delete.html", {"rechamada": rechamada})


# --- Schedule integration --------------------------------------------------------


@requires_permission(Module.RECALLS, Action.VIEW)
def summary(request):
    """Number of pending recalls per day, for the schedule day headers."""
    since, until = _date(request.GET.get("start", "")[:10]), _date(request.GET.get("end", "")[:10])
    if since is None or until is None or not 0 < (until - since).days <= 62:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    contagem = {}
    pendentes = Recall.objects.filter(
        done=False, date__gte=since, date__lt=until, patient__archived=False
    )
    for date in pendentes.values_list("date", flat=True):
        contagem[date.isoformat()] = contagem.get(date.isoformat(), 0) + 1
    return JsonResponse(contagem)


@requires_permission(Module.RECALLS, Action.VIEW)
def of_day(request):
    day = _date(request.GET.get("date"))
    if day is None:
        return HttpResponse(_("Data inválida."), status=400)
    rechamadas = Recall.objects.filter(date=day, patient__archived=False).select_related("patient")
    return render(request, "recalls/_today.html", {"dia": day, "rechamadas": rechamadas})
