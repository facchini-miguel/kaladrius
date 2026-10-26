from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .forms import TipoAtendimentoForm
from .models import TipoAtendimento


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def tipos(request):
    return render(request, "agenda/tipos.html", {"tipos": TipoAtendimento.objects.all()})


@exige_permissao(Modulo.CADASTROS, Acao.CRIAR)
def tipo_novo(request):
    return _formulario(request, TipoAtendimento())


@exige_permissao(Modulo.CADASTROS, Acao.ALTERAR)
def tipo_editar(request, pk):
    return _formulario(request, get_object_or_404(TipoAtendimento.objects, pk=pk))


def _formulario(request, tipo):
    form = TipoAtendimentoForm(request.POST or None, instance=tipo, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Tipo de atendimento {tipo.nome} salvo.")
        return redirect("agenda:tipos")
    return render(request, "agenda/tipo_form.html", {"form": form, "tipo": tipo})


@exige_permissao(Modulo.CADASTROS, Acao.EXCLUIR)
def tipo_excluir(request, pk):
    tipo = get_object_or_404(TipoAtendimento.objects, pk=pk)
    if request.method == "POST":
        try:
            tipo.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{tipo.nome} já foi usado em agendamentos e não pode ser excluído. "
                "Desmarque “ativo” para escondê-lo.",
            )
        else:
            messages.success(request, f"Tipo de atendimento {tipo.nome} excluído.")
        return redirect("agenda:tipos")
    return render(request, "agenda/tipo_excluir.html", {"tipo": tipo})
