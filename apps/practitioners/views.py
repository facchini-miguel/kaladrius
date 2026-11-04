from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissions import Acao, Modulo, exige_permissao

from .forms import ProfissionalForm
from .models import Practitioner


@exige_permissao(Modulo.PROFISSIONAIS, Acao.VER)
def lista(request):
    profissionais = Practitioner.objects.select_related("user")
    return render(request, "practitioners/list.html", {"profissionais": profissionais})


@exige_permissao(Modulo.PROFISSIONAIS, Acao.CRIAR)
def novo(request):
    return _formulario(request, Practitioner())


@exige_permissao(Modulo.PROFISSIONAIS, Acao.ALTERAR)
def editar(request, pk):
    # Profissional.objects only sees the current clinic: other clinics' ids give 404.
    return _formulario(request, get_object_or_404(Practitioner.objects, pk=pk))


def _formulario(request, practitioner):
    form = ProfissionalForm(request.POST or None, instance=practitioner, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profissional %(nome)s salvo.") % {"nome": practitioner.name})
        return redirect("practitioners:list")
    return render(request, "practitioners/form.html", {"form": form, "practitioner": practitioner})


@exige_permissao(Modulo.PROFISSIONAIS, Acao.EXCLUIR)
def excluir(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    if request.method == "POST":
        try:
            practitioner.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "%(nome)s tem registros ligados e não pode ser excluído. "
                    "Desmarque “ativo” para escondê-lo."
                )
                % {"nome": practitioner.name},
            )
        else:
            messages.success(
                request, _("Profissional %(nome)s excluído.") % {"nome": practitioner.name}
            )
        return redirect("practitioners:list")
    return render(request, "practitioners/delete.html", {"practitioner": practitioner})
