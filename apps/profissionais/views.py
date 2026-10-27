from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .forms import ProfissionalForm
from .models import Profissional


@exige_permissao(Modulo.PROFISSIONAIS, Acao.VER)
def lista(request):
    profissionais = Profissional.objects.select_related("usuario")
    return render(request, "profissionais/lista.html", {"profissionais": profissionais})


@exige_permissao(Modulo.PROFISSIONAIS, Acao.CRIAR)
def novo(request):
    return _formulario(request, Profissional())


@exige_permissao(Modulo.PROFISSIONAIS, Acao.ALTERAR)
def editar(request, pk):
    # Profissional.objects only sees the current clinic: other clinics' ids give 404.
    return _formulario(request, get_object_or_404(Profissional.objects, pk=pk))


def _formulario(request, profissional):
    form = ProfissionalForm(request.POST or None, instance=profissional, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profissional %(nome)s salvo.") % {"nome": profissional.nome})
        return redirect("profissionais:lista")
    return render(request, "profissionais/form.html", {"form": form, "profissional": profissional})


@exige_permissao(Modulo.PROFISSIONAIS, Acao.EXCLUIR)
def excluir(request, pk):
    profissional = get_object_or_404(Profissional.objects, pk=pk)
    if request.method == "POST":
        try:
            profissional.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "%(nome)s tem registros ligados e não pode ser excluído. "
                    "Desmarque “ativo” para escondê-lo."
                )
                % {"nome": profissional.nome},
            )
        else:
            messages.success(
                request, _("Profissional %(nome)s excluído.") % {"nome": profissional.nome}
            )
        return redirect("profissionais:lista")
    return render(request, "profissionais/excluir.html", {"profissional": profissional})
