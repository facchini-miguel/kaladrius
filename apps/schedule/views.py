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
    today = timezone.localdate().isoformat()
    return lembrada.get("data", "") if lembrada.get("em") == today else ""


def _resposta_sucesso(message):
    """Empty HTMX response that tells the page to close the modal and reload events."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps({"agendaAtualizada": {"mensagem": message}})
    return response


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
    config = {
        "practitioner": practitioner.pk if practitioner else None,
        "start": clinic.schedule_start.strftime("%H:%M:%S"),
        "end": clinic.schedule_end.strftime("%H:%M:%S"),
        "intervalo": clinic.schedule_interval,
        "date": request.GET.get("date") or _data_lembrada(request),
        # FullCalendar locale and the texts its script shows (badges in the day headers).
        "language": get_language(),
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
            "configuracao": config,
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
                "id": appointment.pk,
                "title": appointment.titulo,
                "start": _relogio(appointment.start),
                "end": _relogio(appointment.end),
                "backgroundColor": appointment.kind.color,
                "borderColor": appointment.kind.color,
                "textColor": "#212529",
                "classNames": [f"situacao-{appointment.status}"],
                "extendedProps": {
                    "kind": appointment.kind.nome_exibido,
                    "description": appointment.description,
                    "status": appointment.status,
                    "status_name": appointment.get_status_display(),
                    "url": reverse("schedule:edit", args=[appointment.pk]),
                },
            }
            for appointment in agendamentos
        ],
        safe=False,
    )


@exige_permissao(Modulo.AGENDA, Acao.CRIAR)
def new(request):
    inicial = {
        field: request.GET[parametro]
        for field, parametro in [
            ("practitioner", "practitioner"),
            ("date", "date"),
            ("start_time", "start"),
            ("end_time", "end"),
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
    return render(request, "schedule/_form.html", {"form": form, "appointment": form.instance})


@exige_permissao(Modulo.AGENDA, Acao.ALTERAR)
def editar(request, pk):
    appointment = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient"), pk=pk
    )
    form = AgendamentoForm(
        request.POST or None,
        instance=appointment,
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
    return render(request, "schedule/_form.html", {"form": form, "appointment": appointment})


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
    appointment = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient", "practitioner"), pk=pk
    )
    try:
        services.marcar(appointment, request.POST.get("status", ""))
    except ValidationError as error:
        if request.headers.get("HX-Request"):
            # Back to the appointment window, with the reason.
            appointment.refresh_from_db()
            form = AgendamentoForm(
                instance=appointment,
                clinic=request.clinic,
                profissionais=services.profissionais_visiveis(request),
            )
            context = {"form": form, "appointment": appointment, "erro_situacao": error.messages[0]}
            return render(request, "schedule/_form.html", context)
        messages.error(request, error.messages[0])
        return redirect("home")
    message = MENSAGENS_SITUACAO[appointment.status] % {"nome": appointment.patient.name}
    if request.headers.get("HX-Request"):
        return _resposta_sucesso(message)
    messages.success(request, message)
    return redirect("home")


@exige_permissao(Modulo.AGENDA, Acao.EXCLUIR)
def excluir(request, pk):
    appointment = get_object_or_404(
        services.agendamentos_visiveis(request).select_related("patient"), pk=pk
    )
    if request.method == "POST":
        excluidos = Appointment.objects.filter(pk=appointment.pk)
        if request.POST.get("escopo") == "serie" and appointment.series:
            # This one and the following ones of the same series.
            excluidos = Appointment.objects.filter(
                series=appointment.series, start__gte=appointment.start
            )
        total, _ = excluidos.delete()
        return _resposta_sucesso(
            ngettext("Agendamento excluído.", "%(n)s agendamentos excluídos.", total) % {"n": total}
        )
    proximos = 0
    if appointment.series:
        proximos = Appointment.objects.filter(
            series=appointment.series, start__gt=appointment.start
        ).count()
    return render(
        request, "schedule/_delete.html", {"appointment": appointment, "proximos": proximos}
    )


def _aniversariantes_em(days):
    """{date: [patients]} for active patients whose birthday falls on the given days."""
    filtro = Q()
    for day in days:
        filtro |= Q(birth_date__month=day.month, birth_date__day=day.day)
    resultado = {day: [] for day in days}
    if not days:
        return resultado
    pacientes = Patient.objects.filter(filtro, active=True, archived=False).order_by("name")
    por_mes_dia = {(day.month, day.day): day for day in days}
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
    days = [start + datetime.timedelta(days=n) for n in range(total_dias)]
    return JsonResponse(
        {
            day.isoformat(): len(results)
            for day, results in _aniversariantes_em(days).items()
            if results
        }
    )


@exige_permissao(Modulo.AGENDA, Acao.VER)
def aniversariantes_dia(request):
    try:
        day = datetime.date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return HttpResponse(_("Data inválida."), status=400)
    aniversariantes = [
        (patient, day.year - patient.birth_date.year) for patient in _aniversariantes_em([day])[day]
    ]
    return render(
        request, "schedule/_birthdays.html", {"dia": day, "aniversariantes": aniversariantes}
    )
