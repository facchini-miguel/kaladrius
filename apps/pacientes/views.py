from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode

from apps.core.permissoes import Acao, Modulo, exige_permissao
from apps.core.validadores import normalizar_cnpj

from .forms import PacienteForm
from .models import Paciente

POR_PAGINA = 50
SITUACOES = {"ativos": Q(ativo=True), "inativos": Q(ativo=False), "todos": Q()}


def filtrar(pacientes, busca, tipo, situacao):
    """Search by name/company name (accent-insensitive), CPF/CNPJ prefix or patient code."""
    if busca:
        filtro = Q(nome__unaccent__icontains=busca) | Q(razao_social__unaccent__icontains=busca)
        documento = normalizar_cnpj(busca)
        if len(documento) >= 3 and not any(c.isspace() for c in busca.strip()):
            filtro |= Q(cpf_cnpj__startswith=documento)
        if busca.isdigit() and len(busca) <= 9:
            filtro |= Q(pk=int(busca))
        pacientes = pacientes.filter(filtro)
    if tipo in Paciente.Tipo.values:
        pacientes = pacientes.filter(tipo=tipo)
    return pacientes.filter(SITUACOES.get(situacao, SITUACOES["ativos"]))


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def lista(request):
    busca = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "")
    situacao = request.GET.get("situacao", "ativos")
    pacientes = filtrar(Paciente.objects.select_related("cidade__uf"), busca, tipo, situacao)
    pagina = Paginator(pacientes, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "pacientes/lista.html",
        {
            "pagina": pagina,
            "busca": busca,
            "tipo": tipo,
            "situacao": situacao,
            "tipos": Paciente.Tipo.choices,
            "parametros": urlencode({"q": busca, "tipo": tipo, "situacao": situacao}),
        },
    )


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def ficha(request, pk):
    paciente = get_object_or_404(
        Paciente.objects.select_related("cidade__uf", "estado_civil"), pk=pk
    )
    return render(request, "pacientes/ficha.html", {"paciente": paciente})


@exige_permissao(Modulo.PACIENTES, Acao.CRIAR)
def novo(request):
    return _formulario(request, Paciente())


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def editar(request, pk):
    return _formulario(request, get_object_or_404(Paciente.objects, pk=pk))


def _formulario(request, paciente):
    form = PacienteForm(request.POST or None, instance=paciente, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        paciente = form.save()
        messages.success(request, f"Paciente {paciente.nome} salvo.")
        return redirect("pacientes:ficha", pk=paciente.pk)
    return render(request, "pacientes/form.html", {"form": form, "paciente": paciente})


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def excluir(request, pk):
    paciente = get_object_or_404(Paciente.objects, pk=pk)
    if request.method == "POST":
        try:
            paciente.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{paciente.nome} tem registros ligados (agenda, rechamadas) e não pode ser "
                "excluído. Desmarque “ativo” para escondê-lo.",
            )
            return redirect("pacientes:ficha", pk=paciente.pk)
        messages.success(request, f"Paciente {paciente.nome} excluído.")
        return redirect("pacientes:lista")
    return render(request, "pacientes/excluir.html", {"paciente": paciente})
