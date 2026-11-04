import datetime
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy, ngettext
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.permissions import Acao, Modulo, exige_permissao, pode, so_a_propria_agenda
from apps.patients.models import Patient

from . import services
from .forms import AgendamentoForm, TipoAtendimentoForm
from .models import Appointment, AppointmentType


@exige_permissao(Modulo.CADASTROS, Acao.VER)
def tipos(request):
    return render(request, "schedule/types.html", {"tipos": AppointmentType.objects.all()})


@exige_permissao(Modulo.CADASTROS, Acao.CRIAR)
def tipo_novo(request):
    return _formulario(request, AppointmentType())


@exige_permissao(Modulo.CADASTROS, Acao.ALTERAR)
def tipo_editar(request, pk):
    return _formulario(request, get_object_or_404(AppointmentType.objects, pk=pk))


def _formulario(request, kind):
    form = TipoAtendimentoForm(request.POST or None, instance=kind, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Tipo de atendimento %(nome)s salvo.") % {"nome": kind.nome_exibido}
        )
        return redirect("schedule:types")
    return render(request, "schedule/type_form.html", {"form": form, "kind": kind})


@exige_permissao(Modulo.CADASTROS, Acao.EXCLUIR)
def tipo_excluir(request, pk):
    kind = get_object_or_404(AppointmentType.objects, pk=pk)
    if request.method == "POST":
        try:
            kind.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "%(nome)s já foi usado em agendamentos e não pode ser excluído. "
                    "Desmarque “ativo” para escondê-lo."
                )
                % {"nome": kind.nome_exibido},
            )
        else:
            messages.success(
                request, _("Tipo de atendimento %(nome)s excluído.") % {"nome": kind.nome_exibido}
            )
        return redirect("schedule:types")
    return render(request, "schedule/type_delete.html", {"kind": kind})


# --- Schedule ----------------------------------------------------------------------

SESSAO_PROFISSIONAL = "agenda_profissional"
# The week last looked at, as in the legacy system: leaving the schedule and coming back
# shows it again. Only on the same day; the next day the schedule opens on today.
SESSAO_DATA = "agenda_data"


def _data_lembrada(request):
    lembrada = request.session.get(SESSAO_DATA) or {}
    hoje = timezone.localdate().isoformat()
    return lembrada.get("data", "") if lembrada.get("em") == hoje else ""


def _resposta_sucesso(mensagem):
    """Empty HTMX response that tells the page to close the modal and reload events."""
    resposta = HttpResponse(status=204)
    resposta["HX-Trigger"] = json.dumps({"agendaAtualizada": {"mensagem": mensagem}})
    return resposta


def _relogio(timestamp):
    """A moment as the clinic's wall clock, without an offset (decision 117): the calendar runs
    in UTC mode, so it shows the clinic's times whatever the browser's time zone."""
    return timezone.localtime(timestamp).replace(tzinfo=None).isoformat()


def _periodo(request):
    """The [start, end) range FullCalendar asks for, as aware datetimes. The calendar runs in UTC
    mode with the clinic's wall clock (decision 117), so any offset that comes along is dropped
    and the bounds are read in the clinic's time zone."""
    try:
        start = datetime.datetime.fromisoformat(request.GET["start"])
        end = datetime.datetime.fromisoformat(request.GET["end"])
    except (KeyError, ValueError):
        return None
    start, end = (timezone.make_aware(timestamp.replace(tzinfo=None)) for timestamp in (start, end))
    if end <= start or end - start > datetime.timedelta(days=62):
        return None
    return start, end


@exige_permissao(Modulo.AGENDA, Acao.VER)
def calendario(request):
    profissionais = list(services.profissionais_visiveis(request).filter(active=True))
    escolhido = request.GET.get("practitioner") or request.session.get(SESSAO_PROFISSIONAL)
    practitioner = next(
        (p for p in profissionais if str(p.pk) == str(escolhido)),
        profissionais[0] if profissionais else None,
    )
    if practitioner is not None:
        request.session[SESSAO_PROFISSIONAL] = practitioner.pk
    clinic = request.clinic
    ver_rechamadas = pode(request, Modulo.RECHAMADAS, Acao.VER)
    configuracao = {
        "practitioner": practitioner.pk if practitioner else None,
        "start": clinic.agenda_inicio.strftime("%H:%M:%S"),
        "end": clinic.agenda_fim.strftime("%H:%M:%S"),
        "intervalo": clinic.agenda_intervalo,
        "date": request.GET.get("date") or _data_lembrada(request),
        # FullCalendar locale and the texts its script shows (badges in the day headers).
        "idioma": get_language(),
        # "Now" on the clinic's wall clock: the calendar runs in UTC mode (decision 117).
        "agora": _relogio(timezone.now()),
        "textos": {
            "aniversariantes": _("aniversariante(s)"),
            "rechamadas": _("rechamada(s) pendente(s)"),
        },
        "pode": {acao: pode(request, Modulo.AGENDA, acao) for acao in ("criar", "alterar")},
        "urls": {
            "eventos": reverse("schedule:events"),
            "novo": reverse("schedule:new"),
            "aniversariantes": reverse("schedule:birthdays"),
            "aniversariantes_dia": reverse("schedule:birthdays_today"),
            "rechamadas": reverse("recalls:summary") if ver_rechamadas else None,
            "rechamadas_dia": reverse("recalls:today") if ver_rechamadas else None,
        },
    }
    return render(
        request,
        "schedule/calendar.html",
        {
            "profissionais": profissionais,
            "practitioner": practitioner,
            "tipos": AppointmentType.objects.filter(active=True),
            "configuracao": configuracao,
            "so_a_propria": so_a_propria_agenda(request),
        },
    )


@exige_permissao(Modulo.AGENDA, Acao.VER)
def eventos(request):
    periodo = _periodo(request)
    practitioner = request.GET.get("practitioner", "")
    if periodo is None or not practitioner.isdecimal():
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start, end = periodo
    # The middle of the visible range falls inside the week (or month) on the screen.
    meio = timezone.localtime(start + (end - start) / 2).date()
    request.session[SESSAO_DATA] = {
        "data": meio.isoformat(),
        "em": timezone.localdate().isoformat(),
    }
    agendamentos = (
        services.agendamentos_visiveis(request)
        .filter(practitioner_id=int(practitioner), start__lt=end, end__gt=start)
        .select_related("kind", "patient")
    )
    return JsonResponse(
        [
            {
                "id": agendamento.pk,
                "title": agendamento.titulo,
                "start": _relogio(agendamento.start),
                "end": _relogio(agendamento.end),
                "backgroundColor": agendamento.kind.color,
                "borderColor": agendamento.kind.color,
                "textColor": "#212529",
                "classNames": [f"situacao-{agendamento.status}"],
                "extendedProps": {
                    "kind": agendamento.kind.nome_exibido,
                    "description": agendamento.description,
                    "status": agendamento.status,
                    "status_name": agendamento.get_status_display(),
                    "url": reverse("schedule:edit", args=[agendamento.pk]),
                },
            }
            for agendamento in agendamentos
        ],
        safe=False,
    )


@exige_permissao(Modulo.AGENDA, Acao.CRIAR)
def novo(request):
    inicial = {
        campo: request.GET[parametro]
        for campo, parametro in [
            ("practitioner", "practitioner"),
            ("date", "date"),
            ("hora_inicio", "start"),
            ("hora_fim", "end"),
        ]
        if request.GET.get(parametro)
    }
    form = AgendamentoForm(
        request.POST or None,
        initial=inicial,
        instance=Appointment(),
        clinic=request.clinic,
        profissionais=services.profissionais_visiveis(request),
    )
    if request.method == "POST" and form.is_valid():
        try:
            criados = services.criar(form.instance, form.intervalos, request.user)
        except IntegrityError:
            form.add_error(
                None, _("Outro agendamento acabou de ocupar este horário. Nada foi gravado.")
            )
        else:
            total = len(criados)
            return _resposta_sucesso(
                ngettext("Agendamento criado.", "%(n)s agendamentos criados.", total) % {"n": total}
            )
    return render(request, "schedule/_form.html", {"form": form, "agendamento": form.instance})


@exige_permissao(Modulo.AGENDA, Acao.ALTERAR)
def editar(request, pk):
    agendamento = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient"), pk=pk
    )
    form = AgendamentoForm(
        request.POST or None,
        instance=agendamento,
        clinic=request.clinic,
        profissionais=services.profissionais_visiveis(request),
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(
                None, _("Outro agendamento acabou de ocupar este horário. Nada foi gravado.")
            )
        else:
            return _resposta_sucesso(_("Agendamento alterado."))
    return render(request, "schedule/_form.html", {"form": form, "agendamento": agendamento})


MENSAGENS_SITUACAO = {
    Appointment.Situacao.AGENDADO: gettext_lazy("%(nome)s: marcação de presença desfeita."),
    Appointment.Situacao.COMPARECEU: gettext_lazy("%(nome)s compareceu."),
    Appointment.Situacao.FALTOU: gettext_lazy("%(nome)s faltou."),
    Appointment.Situacao.DESMARCOU: gettext_lazy("%(nome)s desmarcou. O horário ficou livre."),
}


@require_POST
@exige_permissao(Modulo.AGENDA, Acao.ALTERAR)
def status(request, pk):
    """Came / missed / cancelled, from the appointment window or the home page."""
    agendamento = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient", "practitioner"), pk=pk
    )
    try:
        services.marcar(agendamento, request.POST.get("status", ""))
    except ValidationError as erro:
        if request.headers.get("HX-Request"):
            # Back to the appointment window, with the reason.
            agendamento.refresh_from_db()
            form = AgendamentoForm(
                instance=agendamento,
                clinic=request.clinic,
                profissionais=services.profissionais_visiveis(request),
            )
            contexto = {"form": form, "agendamento": agendamento, "erro_situacao": erro.messages[0]}
            return render(request, "schedule/_form.html", contexto)
        messages.error(request, erro.messages[0])
        return redirect("home")
    mensagem = MENSAGENS_SITUACAO[agendamento.status] % {"nome": agendamento.patient.name}
    if request.headers.get("HX-Request"):
        return _resposta_sucesso(mensagem)
    messages.success(request, mensagem)
    return redirect("home")


@exige_permissao(Modulo.AGENDA, Acao.EXCLUIR)
def excluir(request, pk):
    agendamento = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient"), pk=pk
    )
    if request.method == "POST":
        excluidos = Appointment.objects.filter(pk=agendamento.pk)
        if request.POST.get("escopo") == "serie" and agendamento.serie:
            # This one and the following ones of the same series.
            excluidos = Appointment.objects.filter(
                serie=agendamento.serie, start__gte=agendamento.start
            )
        total, _ = excluidos.delete()
        return _resposta_sucesso(
            ngettext("Agendamento excluído.", "%(n)s agendamentos excluídos.", total) % {"n": total}
        )
    proximos = 0
    if agendamento.serie:
        proximos = Appointment.objects.filter(
            serie=agendamento.serie, start__gt=agendamento.start
        ).count()
    return render(
        request, "schedule/_delete.html", {"agendamento": agendamento, "proximos": proximos}
    )


def _aniversariantes_em(dias):
    """{date: [patients]} for active patients whose birthday falls on the given days."""
    filtro = Q()
    for dia in dias:
        filtro |= Q(birth_date__month=dia.month, birth_date__day=dia.day)
    resultado = {dia: [] for dia in dias}
    if not dias:
        return resultado
    pacientes = Patient.objects.filter(filtro, active=True, archived=False).order_by("name")
    por_mes_dia = {(dia.month, dia.day): dia for dia in dias}
    for patient in pacientes:
        nascimento = patient.birth_date
        resultado[por_mes_dia[(nascimento.month, nascimento.day)]].append(patient)
    return resultado


@exige_permissao(Modulo.AGENDA, Acao.VER)
def aniversariantes(request):
    """Number of birthdays per day in the period shown by the calendar."""
    periodo = _periodo(request)
    if periodo is None:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start = timezone.localdate(periodo[0])
    total_dias = (timezone.localdate(periodo[1]) - start).days
    dias = [start + datetime.timedelta(days=n) for n in range(total_dias)]
    return JsonResponse(
        {dia.isoformat(): len(lista) for dia, lista in _aniversariantes_em(dias).items() if lista}
    )


@exige_permissao(Modulo.AGENDA, Acao.VER)
def aniversariantes_dia(request):
    try:
        dia = datetime.date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return HttpResponse(_("Data inválida."), status=400)
    aniversariantes = [
        (patient, dia.year - patient.birth_date.year) for patient in _aniversariantes_em([dia])[dia]
    ]
    return render(
        request, "schedule/_birthdays.html", {"dia": dia, "aniversariantes": aniversariantes}
    )
