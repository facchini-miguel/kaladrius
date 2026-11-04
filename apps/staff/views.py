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
    for funcionario in funcionarios:
        funcionario.salario_atual = funcionario.salario_em(hoje)
    return render(request, "staff/list.html", {"funcionarios": funcionarios})


@exige_permissao(Modulo.PESSOAL, Acao.VER)
def funcionario(request, pk):
    funcionario = get_object_or_404(Employee.objects, pk=pk)
    return render(
        request,
        "staff/employee.html",
        {
            "funcionario": funcionario,
            "salarios": funcionario.salarios.select_related("created_by"),
            "folhas": funcionario.folhas.select_related("lancamento")[:24],
            "salario_atual": funcionario.salario_em(timezone.localdate()),
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
            funcionario = form.save()
            if form.cleaned_data.get("salario"):
                Salary.objects.create(
                    funcionario=funcionario,
                    valor=form.cleaned_data["salario"],
                    desde=form.cleaned_data["salario_desde"],
                    created_by=request.user,
                )
        messages.success(request, _("%(nome)s salvo.") % {"nome": funcionario.nome})
        return redirect("staff:employee", pk=funcionario.pk)
    return render(request, "staff/form.html", {"form": form, "instancia": instancia})


@exige_permissao(Modulo.PESSOAL, Acao.VER)
def folha(request):
    """The month's pay: one line per employee; save it, then launch it into finance."""
    hoje = timezone.localdate()
    competencia = services.mes_da_url(request.GET.get("mes"), hoje)
    url = f"{reverse('staff:payroll')}?mes={competencia:%Y-%m}"
    pode_alterar = pode(request, Modulo.PESSOAL, Acao.ALTERAR)
    folhas = (
        services.preparar(competencia)
        if pode_alterar
        else list(
            Payroll.objects.filter(competencia=competencia).select_related(
                "funcionario", "lancamento"
            )
        )
    )
    dados = request.POST if request.method == "POST" else None
    linhas = [
        (
            f,
            None
            if f.lancada or not pode_alterar
            # By employee: a sheet not saved yet has no pk.
            else FolhaForm(dados, instance=f, prefix=f"f{f.funcionario_id}"),
        )
        for f in folhas
    ]
    lancar_form = LancarForm(
        dados if dados and dados.get("acao") == "lancar" else None,
        initial={"vencimento": services.fim_do_mes(competencia) + datetime.timedelta(days=5)},
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
                        categoria=lancar_form.cleaned_data["categoria"],
                        vencimento=lancar_form.cleaned_data["vencimento"],
                        usuario=request.user,
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
    anterior = (competencia - datetime.timedelta(days=1)).replace(day=1)
    proximo = services.fim_do_mes(competencia) + datetime.timedelta(days=1)
    return render(
        request,
        "staff/payroll.html",
        {
            "competencia": competencia,
            "linhas": linhas,
            "lancar_form": lancar_form,
            "pode_alterar": pode_alterar,
            "pendentes": any(form is not None for _folha, form in linhas),
            "total": sum((f.total for f in folhas), start=0),
            "anterior": anterior,
            "proximo": proximo,
        },
    )
