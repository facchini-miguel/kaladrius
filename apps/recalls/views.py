import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.permissions import Acao, Modulo, exige_permissao

from .forms import RechamadaForm
from .models import Recall

POR_PAGINA = 50
SITUACOES = {"pendentes": {"concluida": False}, "concluidas": {"concluida": True}, "todas": {}}


def _data(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def _voltar(request, padrao="recalls:list"):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def lista(request):
    status = request.GET.get("status", "pendentes")
    busca = request.GET.get("q", "").strip()
    de, until = _data(request.GET.get("de")), _data(request.GET.get("until"))
    rechamadas = Recall.objects.select_related("patient").filter(
        **SITUACOES.get(status, SITUACOES["pendentes"]), patient__archived=False
    )
    if busca:
        rechamadas = rechamadas.filter(patient__name__unaccent__icontains=busca)
    if de:
        rechamadas = rechamadas.filter(date__gte=de)
    if until:
        rechamadas = rechamadas.filter(date__lte=until)
    pagina = Paginator(rechamadas, POR_PAGINA).get_page(request.GET.get("pagina"))
    filtros = {
        "q": busca,
        "status": status,
        "de": de.isoformat() if de else "",
        "until": until.isoformat() if until else "",
    }
    return render(
        request,
        "recalls/list.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "parametros": urlencode(filtros),
            "hoje": timezone.localdate(),
        },
    )


@exige_permissao(Modulo.RECHAMADAS, Acao.CRIAR)
def novo(request):
    inicial = {"date": request.GET.get("date") or ""}
    if request.GET.get("patient", "").isdecimal():
        inicial["patient"] = request.GET["patient"]
    return _formulario(request, Recall(created_by=request.user), inicial)


@exige_permissao(Modulo.RECHAMADAS, Acao.ALTERAR)
def editar(request, pk):
    return _formulario(request, get_object_or_404(Recall.objects, pk=pk), {})


def _formulario(request, rechamada, inicial):
    form = RechamadaForm(
        request.POST or None, instance=rechamada, initial=inicial, clinic=request.clinic
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Rechamada de %(nome)s salva.") % {"nome": rechamada.patient.name}
        )
        return _voltar(request)
    patient = rechamada.patient if rechamada.patient_id else form["patient"].value()
    if patient and not hasattr(patient, "name"):
        # Raw value from the hidden field: may be anything when the request is tampered with.
        code = str(patient)
        consulta = form.fields["patient"].queryset
        patient = consulta.filter(pk=int(code)).first() if code.isdecimal() else None
    return render(
        request,
        "recalls/form.html",
        {
            "form": form,
            "rechamada": rechamada,
            "patient": patient,
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
@exige_permissao(Modulo.RECHAMADAS, Acao.ALTERAR)
def concluir(request, pk):
    rechamada = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    rechamada.concluida = not rechamada.concluida
    rechamada.save(update_fields=["concluida", "updated_at"])
    if rechamada.concluida:
        mensagem = _("Rechamada de %(nome)s concluída.")
    else:
        mensagem = _("Rechamada de %(nome)s reaberta.")
    messages.success(request, mensagem % {"nome": rechamada.patient.name})
    return _voltar(request)


@exige_permissao(Modulo.RECHAMADAS, Acao.EXCLUIR)
def excluir(request, pk):
    rechamada = get_object_or_404(Recall.objects.select_related("patient"), pk=pk)
    if request.method == "POST":
        rechamada.delete()
        messages.success(
            request, _("Rechamada de %(nome)s excluída.") % {"nome": rechamada.patient.name}
        )
        return _voltar(request)
    return render(request, "recalls/delete.html", {"rechamada": rechamada})


# --- Schedule integration --------------------------------------------------------


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def resumo(request):
    """Number of pending recalls per day, for the schedule day headers."""
    de, until = _data(request.GET.get("start", "")[:10]), _data(request.GET.get("end", "")[:10])
    if de is None or until is None or not 0 < (until - de).days <= 62:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    contagem = {}
    pendentes = Recall.objects.filter(
        concluida=False, date__gte=de, date__lt=until, patient__archived=False
    )
    for date in pendentes.values_list("date", flat=True):
        contagem[date.isoformat()] = contagem.get(date.isoformat(), 0) + 1
    return JsonResponse(contagem)


@exige_permissao(Modulo.RECHAMADAS, Acao.VER)
def do_dia(request):
    dia = _data(request.GET.get("date"))
    if dia is None:
        return HttpResponse(_("Data inválida."), status=400)
    rechamadas = Recall.objects.filter(date=dia, patient__archived=False).select_related("patient")
    return render(request, "recalls/_today.html", {"dia": dia, "rechamadas": rechamadas})
