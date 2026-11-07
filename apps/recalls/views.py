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
STATUSES = {"pending": {"done": False}, "done": {"done": True}, "all": {}}


def _date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def _back(request, default="recalls:list"):
    destination = request.POST.get("next") or request.GET.get("next")
    if destination and url_has_allowed_host_and_scheme(
        destination, allowed_hosts={request.get_host()}
    ):
        return redirect(destination)
    return redirect(default)


@requires_permission(Module.RECALLS, Action.VIEW)
def recall_list(request):
    status = request.GET.get("status", "pending")
    search = request.GET.get("q", "").strip()
    since, until = _date(request.GET.get("since")), _date(request.GET.get("until"))
    recalls = Recall.objects.select_related("patient").filter(
        **STATUSES.get(status, STATUSES["pending"]), patient__archived=False
    )
    if search:
        recalls = recalls.filter(patient__name__unaccent__icontains=search)
    if since:
        recalls = recalls.filter(date__gte=since)
    if until:
        recalls = recalls.filter(date__lte=until)
    page = Paginator(recalls, PER_PAGE).get_page(request.GET.get("page"))
    filters = {
        "q": search,
        "status": status,
        "since": since.isoformat() if since else "",
        "until": until.isoformat() if until else "",
    }
    return render(
        request,
        "recalls/list.html",
        {
            "page": page,
            "filters": filters,
            "query": urlencode(filters),
            "today": timezone.localdate(),
        },
    )


@requires_permission(Module.RECALLS, Action.CREATE)
def new_recall(request):
    initial = {"date": request.GET.get("date") or ""}
    if request.GET.get("patient", "").isdecimal():
        initial["patient"] = request.GET["patient"]
    return _recall_form(request, Recall(created_by=request.user), initial)


@requires_permission(Module.RECALLS, Action.CHANGE)
def edit_recall(request, pk):
    return _recall_form(request, get_object_or_404(Recall.objects, pk=pk), {})


def _recall_form(request, recall, initial):
    form = RecallForm(request.POST or None, instance=recall, initial=initial, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Rechamada de %(nome)s salva.") % {"nome": recall.patient.name})
        return _back(request)
    patient = recall.patient if recall.patient_id else form["patient"].value()
    if patient and not hasattr(patient, "name"):
        # Raw value from the hidden field: may be anything when the request is tampered with.
        code = str(patient)
        query = form.fields["patient"].queryset
        patient = query.filter(pk=int(code)).first() if code.isdecimal() else None
    return render(
        request,
        "recalls/form.html",
        {
            "form": form,
            "recall": recall,
            "patient": patient,
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
@requires_permission(Module.RECALLS, Action.CHANGE)
def complete(request, pk):
    recall = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    recall.done = not recall.done
    recall.save(update_fields=["done", "updated_at"])
    if recall.done:
        message = _("Rechamada de %(nome)s concluída.")
    else:
        message = _("Rechamada de %(nome)s reaberta.")
    messages.success(request, message % {"nome": recall.patient.name})
    return _back(request)


@requires_permission(Module.RECALLS, Action.DELETE)
def delete_recall(request, pk):
    recall = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    if request.method == "POST":
        recall.delete()
        messages.success(
            request, _("Rechamada de %(nome)s excluída.") % {"nome": recall.patient.name}
        )
        return _back(request)
    return render(request, "recalls/delete.html", {"recall": recall})


# --- Schedule integration --------------------------------------------------------


@requires_permission(Module.RECALLS, Action.VIEW)
def summary(request):
    """Number of pending recalls per day, for the schedule day headers."""
    since, until = _date(request.GET.get("start", "")[:10]), _date(request.GET.get("end", "")[:10])
    if since is None or until is None or not 0 < (until - since).days <= 62:
        return JsonResponse({"error": _("Parâmetros inválidos.")}, status=400)
    counts = {}
    pending = Recall.objects.filter(
        done=False, date__gte=since, date__lt=until, patient__archived=False
    )
    for date in pending.values_list("date", flat=True):
        counts[date.isoformat()] = counts.get(date.isoformat(), 0) + 1
    return JsonResponse(counts)


@requires_permission(Module.RECALLS, Action.VIEW)
def of_day(request):
    day = _date(request.GET.get("date"))
    if day is None:
        return HttpResponse(_("Data inválida."), status=400)
    recalls = Recall.objects.filter(date=day, patient__archived=False).select_related("patient")
    return render(request, "recalls/_today.html", {"day": day, "recalls": recalls})
