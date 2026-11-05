"""Staff and the month's pay (decision 099): administrators and Finance only."""

import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.core.permissions import Acao, Modulo, exige_permissao, pode

from . import services
from .forms import FolhaForm, FuncionarioForm, LancarForm
from .models import Employee, Payroll, Salary


@exige_permissao(Modulo.PESSOAL, Acao.VER)
def lista(request):
    funcionarios = list(Employee.objects.all())
    hoje = timezone.localdate()
    for employee in funcionarios:
        employee.salario_atual = employee.salario_em(hoje)
    return render(request, "staff/list.html", {"funcionarios": funcionarios})


@exige_permissao(Modulo.PESSOAL, Acao.VER)
def employee(request, pk):
    employee = get_object_or_404(Employee.objects, pk=pk)
    return render(
        request,
        "staff/employee.html",
        {
            "employee": employee,
            "salarios": employee.salarios.select_related("created_by"),
            "folhas": employee.folhas.select_related("entry")[:24],
            "salario_atual": employee.salario_em(timezone.localdate()),
        },
    )


@exige_permissao(Modulo.PESSOAL, Acao.CRIAR)
def novo(request):
    return _formulario(request, Employee())


@exige_permissao(Modulo.PESSOAL, Acao.ALTERAR)
def editar(request, pk):
    return _formulario(request, get_object_or_404(Employee.objects, pk=pk))


def _formulario(request, instancia):
    form = FuncionarioForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            employee = form.save()
            if form.cleaned_data.get("salary"):
                Salary.objects.create(
                    employee=employee,
                    amount=form.cleaned_data["salary"],
                    effective_from=form.cleaned_data["salario_desde"],
                    created_by=request.user,
                )
        messages.success(request, _("%(nome)s salvo.") % {"nome": employee.name})
        return redirect("staff:employee", pk=employee.pk)
    return render(request, "staff/form.html", {"form": form, "instancia": instancia})


@exige_permissao(Modulo.PESSOAL, Acao.VER)
def folha(request):
    """The month's pay: one line per employee; save it, then launch it into finance."""
    hoje = timezone.localdate()
    period = services.mes_da_url(request.GET.get("mes"), hoje)
    url = f"{reverse('staff:payroll')}?mes={period:%Y-%m}"
    pode_alterar = pode(request, Modulo.PESSOAL, Acao.ALTERAR)
    folhas = (
        services.preparar(period)
        if pode_alterar
        else list(Payroll.objects.filter(period=period).select_related("employee", "entry"))
    )
    dados = request.POST if request.method == "POST" else None
    linhas = [
        (
            f,
            None
            if f.lancada or not pode_alterar
            # By employee: a sheet not saved yet has no pk.
            else FolhaForm(dados, instance=f, prefix=f"f{f.employee_id}"),
        )
        for f in folhas
    ]
    lancar_form = LancarForm(
        dados if dados and dados.get("acao") == "lancar" else None,
        initial={"due_date": services.fim_do_mes(period) + datetime.timedelta(days=5)},
    )
    if request.method == "POST":
        if not pode_alterar:
            return redirect(url)
        formularios = [form for _folha, form in linhas if form is not None]
        if all(form.is_valid() for form in formularios):
            with transaction.atomic():
                for form in formularios:
                    form.save()
            if request.POST.get("acao") != "lancar":
                messages.success(request, _("Folha salva."))
                return redirect(url)
            if lancar_form.is_valid():
                try:
                    lancadas = services.lancar(
                        [f for f, form in linhas if form is not None],
                        category=lancar_form.cleaned_data["category"],
                        due_date=lancar_form.cleaned_data["due_date"],
                        user=request.user,
                    )
                except ValidationError as erro:
                    messages.error(request, erro.messages[0])
                else:
                    messages.success(
                        request,
                        ngettext(
                            "%(n)s conta a pagar criada no financeiro.",
                            "%(n)s contas a pagar criadas no financeiro.",
                            lancadas,
                        )
                        % {"n": lancadas},
                    )
                    return redirect(url)
    anterior = (period - datetime.timedelta(days=1)).replace(day=1)
    proximo = services.fim_do_mes(period) + datetime.timedelta(days=1)
    return render(
        request,
        "staff/payroll.html",
        {
            "period": period,
            "linhas": linhas,
            "lancar_form": lancar_form,
            "pode_alterar": pode_alterar,
            "pendentes": any(form is not None for _folha, form in linhas),
            "total": sum((f.total for f in folhas), start=0),
            "anterior": anterior,
            "proximo": proximo,
        },
    )
