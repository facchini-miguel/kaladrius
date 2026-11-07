"""Treatment estimates and the procedure price list (0.18.0).

Estimates belong to the Orcamentos module (practitioners, front desk and administrators);
approving one creates a receivable, so it also needs Recebimentos (not practitioners).
Discounts follow the receivables rule: administrators only. The price list is part of the
Cadastros module (administrators change it, the others only read it).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import modules
from apps.core.models import ModuleCode
from apps.core.permissions import Action, Module, can, requires_permission
from apps.dentistry.teeth import odontogram
from apps.finance.models import Category
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import services
from .forms import ApproveEstimateForm, DiscountForm, EstimateForm, EstimateItemForm, ProcedureForm
from .models import Estimate, Procedure

PER_PAGE = 50


def _estimates():
    # Archived patients leave the team's screens (decision 046).
    return Estimate.objects.filter(patient__archived=False).select_related(
        "patient", "practitioner"
    )


def _open_estimate(request, pk):
    estimate = get_object_or_404(_estimates(), pk=pk)
    if estimate.status != Estimate.Status.OPEN:
        messages.error(request, _("This estimate was already approved or refused."))
        return None, redirect("estimates:detail", pk=estimate.pk)
    return estimate, None


def _dentistry(request):
    # The request's cached modules; the item's save() re-checks under the clinic lock. The
    # system administrator also gets the dental chart with Dentistry off (decision 115).
    return ModuleCode.DENTISTRY in modules.visible(request)


def _allow_if_disabled(request, item):
    """The system administrator writes dental items with Dentistry off; the page says so."""
    if ModuleCode.DENTISTRY not in modules.enabled(request) and _dentistry(request):
        item.dentistry_off_allowed = True


@requires_permission(Module.ESTIMATES, Action.VIEW)
def estimate_list(request):
    status = request.GET.get("status", Estimate.Status.OPEN)
    search = request.GET.get("q", "").strip()
    estimates = _estimates().prefetch_related("items")
    if status in Estimate.Status.values:
        estimates = estimates.filter(status=status)
    if search:
        estimates = estimates.filter(patient__name__unaccent__icontains=search)
    page = Paginator(estimates, PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "estimates/list.html",
        {
            "page": page,
            "status": status,
            "search": search,
            "statuses": Estimate.Status.choices,
            "query": urlencode({"status": status, "q": search}),
        },
    )


@requires_permission(Module.ESTIMATES, Action.CREATE)
def new_estimate(request):
    initial = {}
    code = request.GET.get("patient", "")
    if code.isdecimal():
        initial["patient"] = code
    # A practitioner writes estimates in their own name by default.
    own = Practitioner.objects.filter(user=request.user, active=True).first()
    if own is not None:
        initial["practitioner"] = own.pk
    form = EstimateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.instance.created_by = request.user
        estimate = form.save()
        messages.success(request, _("Estimate created. Now add the procedures."))
        return redirect("estimates:detail", pk=estimate.pk)
    patient_amount = form["patient"].value()
    patient = (
        Patient.objects.filter(pk=patient_amount, archived=False).first()
        if str(patient_amount or "").isdecimal()
        else None
    )
    return render(request, "estimates/form.html", {"form": form, "patient": patient})


@requires_permission(Module.ESTIMATES, Action.CHANGE)
def edit_estimate(request, pk):
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    form = EstimateForm(request.POST or None, instance=estimate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Estimate saved."))
        return redirect("estimates:detail", pk=estimate.pk)
    return render(
        request,
        "estimates/form.html",
        {"form": form, "patient": estimate.patient, "estimate": estimate},
    )


@requires_permission(Module.ESTIMATES, Action.VIEW)
def estimate_detail(request, pk):
    estimate = get_object_or_404(_estimates().prefetch_related("items"), pk=pk)
    is_open = estimate.status == Estimate.Status.OPEN
    dentistry = _dentistry(request)
    if dentistry:
        modules.mark_if_disabled(request, ModuleCode.DENTISTRY)
    # Whoever writes the estimate may also give a discount on its total (0.27.1, decision 074).
    can_discount = can(request, Module.ESTIMATES, Action.CHANGE)
    return render(
        request,
        "estimates/detail.html",
        {
            "estimate": estimate,
            "is_open": is_open,
            "item_form": EstimateItemForm(dentistry=dentistry),
            "dentistry_enabled": dentistry,
            "discount_form": DiscountForm(initial={"discount": estimate.discount})
            if can_discount and is_open
            else None,
            "can_approve": is_open
            and can(request, Module.RECEIVING, Action.CREATE)
            and can(request, Module.ESTIMATES, Action.CHANGE),
            **_teeth(request, estimate),
        },
    )


def _teeth(request, estimate):
    """Dental chart and tooth columns (decision 080): in the Odontologia area, and in any
    area for an estimate that already has teeth (changing the area hides nothing written)."""
    has_history = any(item.teeth or item.faces for item in estimate.items.all())
    if not (_dentistry(request) or has_history):
        return {"show_teeth": False}
    return {"show_teeth": True, **odontogram(estimate.teeth)}


@require_POST
@requires_permission(Module.ESTIMATES, Action.CHANGE)
def add_item(request, pk):
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    form = EstimateItemForm(request.POST, dentistry=_dentistry(request))
    if form.is_valid():
        item = form.save(commit=False)
        item.estimate = estimate
        item.description = form.cleaned_data["description"]
        item.unit_price = form.cleaned_data["unit_price"]
        _allow_if_disabled(request, item)
        try:
            item.save()
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, _("Item added."))
    else:
        errors = [str(error) for estimate_list in form.errors.values() for error in estimate_list]
        messages.error(request, " ".join(errors))
    return redirect("estimates:detail", pk=estimate.pk)


@require_POST
@requires_permission(Module.ESTIMATES, Action.CHANGE)
def remove_item(request, pk, item):
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    record = get_object_or_404(estimate.items, pk=item)
    if (record.teeth or record.faces) and not _dentistry(request):
        raise PermissionDenied
    _allow_if_disabled(request, record)
    try:
        record.delete()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, _("Item removed."))
    return redirect("estimates:detail", pk=estimate.pk)


@require_POST
@requires_permission(Module.ESTIMATES, Action.CHANGE)
def discount(request, pk):
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    form = DiscountForm(request.POST)
    if form.is_valid():
        value = form.cleaned_data["discount"] or 0
        if value > estimate.subtotal:
            messages.error(request, _("The discount exceeds the estimate total."))
        else:
            estimate.discount = value
            estimate.save()
            messages.success(request, _("Discount applied."))
    return redirect("estimates:detail", pk=estimate.pk)


@requires_permission(Module.ESTIMATES, Action.CHANGE)
def approve(request, pk):
    if not can(request, Module.RECEIVING, Action.CREATE):
        raise PermissionDenied
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    item = estimate.items.select_related("procedure__category").first()
    category = (
        item.procedure.category
        if item and item.procedure and item.procedure.category
        else Category.objects.filter(kind=Category.Kind.INCOME, active=True).first()
    )
    form = ApproveEstimateForm(request.POST or None, initial={"category": category})
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        payment = (
            {"method": data["method"], "account": data["account"]} if data["received_now"] else None
        )
        try:
            entry = services.approve(
                estimate,
                installments=data["installments"],
                first_due_date=data["first_due_date"],
                category=data["category"],
                user=request.user,
                payment=payment,
            )
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            messages.success(request, _("Estimate approved and added to Receivables."))
            return redirect("finance:entry", pk=entry.pk)
    return render(request, "estimates/approve.html", {"form": form, "estimate": estimate})


@require_POST
@requires_permission(Module.ESTIMATES, Action.CHANGE)
def refuse(request, pk):
    estimate, response = _open_estimate(request, pk)
    if response:
        return response
    try:
        services.refuse(estimate, user=request.user)
    except ValidationError as error:  # approved or refused by someone else a moment ago
        messages.error(request, error.messages[0])
    else:
        messages.success(request, _("Estimate marked as refused."))
    return redirect("estimates:detail", pk=estimate.pk)


@requires_permission(Module.ESTIMATES, Action.VIEW)
def print_estimate(request, pk):
    estimate = get_object_or_404(_estimates().prefetch_related("items"), pk=pk)
    return render(
        request,
        "estimates/print.html",
        {"estimate": estimate, **_teeth(request, estimate)},
    )


# --- Procedure price list ---------------------------------------------------------------


@requires_permission(Module.CATALOGS, Action.VIEW)
def procedures(request):
    return render(
        request,
        "estimates/procedures.html",
        {"procedures": Procedure.objects.select_related("category")},
    )


@requires_permission(Module.CATALOGS, Action.CHANGE)
def procedure_form(request, pk=None):
    procedure = get_object_or_404(Procedure.objects, pk=pk) if pk else Procedure()
    form = ProcedureForm(request.POST or None, instance=procedure)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Procedure %(name)s saved.") % {"name": form.instance.name})
        return redirect("estimates:procedures")
    return render(
        request,
        "estimates/procedure_form.html",
        {"form": form, "procedure": procedure},
    )
