"""Health plans and patients' cards (decision 094)."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissions import Acao, Modulo, exige_permissao
from apps.patients.models import Paciente

from . import insurance
from .forms import CarteirinhaForm, ConvenioForm
from .models import Carteirinha, Convenio


@exige_permissao(Modulo.CONVENIOS, Acao.VER)
def lista(request):
    convenios = Convenio.objects.annotate(
        pacientes=Count("carteirinhas", filter=Q(carteirinhas__ativa=True))
    )
    return render(
        request,
        "convenios/lista.html",
        {"convenios": convenios, "rotulo_do_registro": insurance.rotulo_do_registro()},
    )


@exige_permissao(Modulo.CONVENIOS, Acao.CRIAR)
def novo(request):
    return _convenio(request, Convenio())


@exige_permissao(Modulo.CONVENIOS, Acao.ALTERAR)
def editar(request, pk):
    return _convenio(request, get_object_or_404(Convenio.objects, pk=pk))


def _convenio(request, instancia):
    form = ConvenioForm(request.POST or None, instance=instancia, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        convenio = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": convenio.nome})
        return redirect("convenios:lista")
    return render(request, "convenios/form.html", {"form": form, "instancia": instancia})


@exige_permissao(Modulo.CONVENIOS, Acao.CRIAR)
def carteirinha_nova(request, paciente):
    paciente = get_object_or_404(Paciente.objects, pk=paciente, arquivado=False)
    return _carteirinha(request, paciente, Carteirinha())


@exige_permissao(Modulo.CONVENIOS, Acao.ALTERAR)
def carteirinha_editar(request, pk):
    carteirinha = get_object_or_404(
        Carteirinha.objects.select_related("paciente"), pk=pk, paciente__arquivado=False
    )
    return _carteirinha(request, carteirinha.paciente, carteirinha)


def _carteirinha(request, paciente, instancia):
    form = CarteirinhaForm(request.POST or None, instance=instancia, paciente=paciente)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Carteirinha salva."))
        return redirect("pacientes:ficha", pk=paciente.pk)
    return render(
        request,
        "convenios/carteirinha_form.html",
        {"form": form, "paciente": paciente, "instancia": instancia},
    )
