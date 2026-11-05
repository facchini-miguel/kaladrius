"""Health plans and patients' cards (decision 094)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissions import Action, Module, requires_permission
from apps.patients.models import Patient

from . import insurance
from .forms import CarteirinhaForm, ConvenioForm
from .models import HealthPlan, MemberCard


@requires_permission(Module.HEALTH_PLANS, Action.VIEW)
def results(request):
    convenios = HealthPlan.objects.annotate(
        pacientes=Count("carteirinhas", filter=Q(carteirinhas__active=True))
    )
    return render(
        request,
        "health_plans/list.html",
        {"convenios": convenios, "rotulo_do_registro": insurance.rotulo_do_registro()},
    )


@requires_permission(Module.HEALTH_PLANS, Action.CREATE)
def new(request):
    return _convenio(request, HealthPlan())


@requires_permission(Module.HEALTH_PLANS, Action.CHANGE)
def editar(request, pk):
    return _convenio(request, get_object_or_404(HealthPlan.objects, pk=pk))


def _convenio(request, instancia):
    form = ConvenioForm(request.POST or None, instance=instancia, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        health_plan = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": health_plan.name})
        return redirect("health_plans:list")
    return render(request, "health_plans/form.html", {"form": form, "instancia": instancia})


@requires_permission(Module.HEALTH_PLANS, Action.CREATE)
def carteirinha_nova(request, patient):
    patient = get_object_or_404(Patient.objects, pk=patient, archived=False)
    return _carteirinha(request, patient, MemberCard())


@requires_permission(Module.HEALTH_PLANS, Action.CHANGE)
def carteirinha_editar(request, pk):
    carteirinha = get_object_or_404(
        MemberCard.objects.select_related("patient"), pk=pk, patient__archived=False
    )
    return _carteirinha(request, carteirinha.patient, carteirinha)


def _carteirinha(request, patient, instancia):
    form = CarteirinhaForm(request.POST or None, instance=instancia, patient=patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Carteirinha salva."))
        return redirect("patients:record", pk=patient.pk)
    return render(
        request,
        "health_plans/card_form.html",
        {"form": form, "patient": patient, "instancia": instancia},
    )
