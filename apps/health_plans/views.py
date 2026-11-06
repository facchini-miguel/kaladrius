"""Health plans and patients' cards (decision 094)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissions import Action, Module, requires_permission
from apps.patients.models import Patient

from . import insurance
from .forms import HealthPlanForm, MemberCardForm
from .models import HealthPlan, MemberCard


@requires_permission(Module.HEALTH_PLANS, Action.VIEW)
def health_plan_list(request):
    convenios = HealthPlan.objects.annotate(
        patient_count=Count("member_cards", filter=Q(member_cards__active=True))
    )
    return render(
        request,
        "health_plans/list.html",
        {"health_plans": convenios, "registration_label": insurance.registration_label()},
    )


@requires_permission(Module.HEALTH_PLANS, Action.CREATE)
def new_health_plan(request):
    return _health_plan_form(request, HealthPlan())


@requires_permission(Module.HEALTH_PLANS, Action.CHANGE)
def edit_health_plan(request, pk):
    return _health_plan_form(request, get_object_or_404(HealthPlan.objects, pk=pk))


def _health_plan_form(request, instancia):
    form = HealthPlanForm(request.POST or None, instance=instancia, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        health_plan = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": health_plan.name})
        return redirect("health_plans:list")
    return render(request, "health_plans/form.html", {"form": form, "instance": instancia})


@requires_permission(Module.HEALTH_PLANS, Action.CREATE)
def new_member_card(request, patient):
    patient = get_object_or_404(Patient.objects, pk=patient, archived=False)
    return _member_card_form(request, patient, MemberCard())


@requires_permission(Module.HEALTH_PLANS, Action.CHANGE)
def edit_member_card(request, pk):
    carteirinha = get_object_or_404(
        MemberCard.objects.select_related("patient"), pk=pk, patient__archived=False
    )
    return _member_card_form(request, carteirinha.patient, carteirinha)


def _member_card_form(request, patient, instancia):
    form = MemberCardForm(request.POST or None, instance=instancia, patient=patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Carteirinha salva."))
        return redirect("patients:record", pk=patient.pk)
    return render(
        request,
        "health_plans/card_form.html",
        {"form": form, "patient": patient, "instance": instancia},
    )
