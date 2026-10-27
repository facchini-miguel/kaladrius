import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.permissoes import Acao, Modulo, exige_permissao

from .forms import RechamadaForm
from .models import Rechamada

POR_PAGINA = 50
SITUACOES = {"pendentes": {"concluida": False}, "concluidas": {"concluida": True}, "todas": {}}


def _data(valor):
    try:
        return datetime.date.fromisoformat(valor or "")
    except ValueError:
        return None


def _voltar(request, padrao="rechamadas:lista"):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def lista(request):
    situacao = request.GET.get("situacao", "pendentes")
    busca = request.GET.get("q", "").strip()
    de, ate = _data(request.GET.get("de")), _data(request.GET.get("ate"))
    rechamadas = Rechamada.objects.select_related("paciente").filter(
        **SITUACOES.get(situacao, SITUACOES["pendentes"]), paciente__arquivado=False
    )
    if busca:
        rechamadas = rechamadas.filter(paciente__nome__unaccent__icontains=busca)
    if de:
        rechamadas = rechamadas.filter(data__gte=de)
    if ate:
        rechamadas = rechamadas.filter(data__lte=ate)
    pagina = Paginator(rechamadas, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = {
        "q": busca,
        "situacao": situacao,
        "de": de.isoformat() if de else "",
        "ate": ate.isoformat() if ate else "",
    }
    return render(
        request,
        "rechamadas/lista.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "parametros": urlencode(filtros),
            "hoje": timezone.localdate(),
        },
    )


@exige_permissao(Modulo.RECHAMADAS, Acao.CRIAR)
def novo(request):
    inicial = {"data": request.GET.get("data") or ""}
    if request.GET.get("paciente", "").isdecimal():
        inicial["paciente"] = request.GET["paciente"]
    return _formulario(request, Rechamada(criado_por=request.user), inicial)


@exige_permissao(Modulo.RECHAMADAS, Acao.ALTERAR)
def editar(request, pk):
    return _formulario(request, get_object_or_404(Rechamada.objects, pk=pk), {})


def _formulario(request, rechamada, inicial):
    form = RechamadaForm(
        request.POST or None, instance=rechamada, initial=inicial, clinica=request.clinica
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Rechamada de %(nome)s salva.") % {"nome": rechamada.paciente.nome}
        )
        return _voltar(request)
    paciente = rechamada.paciente if rechamada.paciente_id else form["paciente"].value()
    if paciente and not hasattr(paciente, "nome"):
        # Raw value from the hidden field: may be anything when the request is tampered with.
        codigo = str(paciente)
        consulta = form.fields["paciente"].queryset
        paciente = consulta.filter(pk=int(codigo)).first() if codigo.isdecimal() else None
    return render(
        request,
        "rechamadas/form.html",
        {
            "form": form,
            "rechamada": rechamada,
            "paciente": paciente,
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
@exige_permissao(Modulo.RECHAMADAS, Acao.ALTERAR)
def concluir(request, pk):
    rechamada = get_object_or_404(Rechamada.objects.select_related("paciente"), pk=pk)
    rechamada.concluida = not rechamada.concluida
    rechamada.save(update_fields=["concluida", "alterado_em"])
    if rechamada.concluida:
        mensagem = _("Rechamada de %(nome)s concluída.")
    else:
        mensagem = _("Rechamada de %(nome)s reaberta.")
    messages.success(request, mensagem % {"nome": rechamada.paciente.nome})
    return _voltar(request)


@exige_permissao(Modulo.RECHAMADAS, Acao.EXCLUIR)
def excluir(request, pk):
    rechamada = get_object_or_404(Rechamada.objects.select_related("paciente"), pk=pk)
    if request.method == "POST":
        rechamada.delete()
        messages.success(
            request, _("Rechamada de %(nome)s excluída.") % {"nome": rechamada.paciente.nome}
        )
        return _voltar(request)
    return render(request, "rechamadas/excluir.html", {"rechamada": rechamada})


# --- Schedule integration --------------------------------------------------------


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def resumo(request):
    """Number of pending recalls per day, for the schedule day headers."""
    de, ate = _data(request.GET.get("start", "")[:10]), _data(request.GET.get("end", "")[:10])
    if de is None or ate is None or not 0 < (ate - de).days <= 62:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    contagem = {}
    pendentes = Rechamada.objects.filter(
        concluida=False, data__gte=de, data__lt=ate, paciente__arquivado=False
    )
    for data in pendentes.values_list("data", flat=True):
        contagem[data.isoformat()] = contagem.get(data.isoformat(), 0) + 1
    return JsonResponse(contagem)


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def do_dia(request):
    dia = _data(request.GET.get("data"))
    if dia is None:
        return HttpResponse(_("Data inválida."), status=400)
    rechamadas = Rechamada.objects.filter(data=dia, paciente__arquivado=False).select_related(
        "paciente"
    )
    return render(request, "rechamadas/_do_dia.html", {"dia": dia, "rechamadas": rechamadas})
