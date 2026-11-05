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

from apps.core.permissions import Action, Module, can, own_schedule_only, requires_permission
from apps.patients.models import Patient

from . import services
from .forms import AppointmentForm, AppointmentTypeForm
from .models import Appointment, AppointmentType


@requires_permission(Module.CATALOGS, Action.VIEW)
def appointment_types(request):
    return render(request, "schedule/types.html", {"tipos": AppointmentType.objects.all()})


@requires_permission(Module.CATALOGS, Action.CREATE)
def new_appointment_type(request):
    return _type_form(request, AppointmentType())


@requires_permission(Module.CATALOGS, Action.CHANGE)
def edit_appointment_type(request, pk):
    return _type_form(request, get_object_or_404(AppointmentType.objects, pk=pk))


def _type_form(request, kind):
    form = AppointmentTypeForm(request.POST or None, instance=kind, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Tipo de atendimento %(nome)s salvo.") % {"nome": kind.display_name}
        )
        return redirect("schedule:types")
    return render(request, "schedule/type_form.html", {"form": form, "kind": kind})


@requires_permission(Module.CATALOGS, Action.DELETE)
def delete_appointment_type(request, pk):
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
                % {"nome": kind.display_name},
            )
        else:
            messages.success(
                request, _("Tipo de atendimento %(nome)s excluído.") % {"nome": kind.display_name}
            )
        return redirect("schedule:types")
    return render(request, "schedule/type_delete.html", {"kind": kind})


# --- Schedule ----------------------------------------------------------------------

SESSION_PRACTITIONER = "agenda_profissional"
# The week last looked at, as in the legacy system: leaving the schedule and coming back
# shows it again. Only on the same day; the next day the schedule opens on today.
SESSION_DATE = "agenda_data"


def _remembered_date(request):
    lembrada = request.session.get(SESSION_DATE) or {}
    today = timezone.localdate().isoformat()
    return lembrada.get("data", "") if lembrada.get("em") == today else ""


def _success_response(message):
    """Empty HTMX response that tells the page to close the modal and reload events."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps({"agendaAtualizada": {"mensagem": message}})
    return response


def _clock(timestamp):
    """A moment as the clinic's wall clock, without an offset (decision 117): the calendar runs
    in UTC mode, so it shows the clinic's times whatever the browser's time zone."""
    return timezone.localtime(timestamp).replace(tzinfo=None).isoformat()


def _range(request):
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


@requires_permission(Module.SCHEDULE, Action.VIEW)
def calendar_view(request):
    profissionais = list(services.visible_practitioners(request).filter(active=True))
    escolhido = request.GET.get("practitioner") or request.session.get(SESSION_PRACTITIONER)
    practitioner = next(
        (p for p in profissionais if str(p.pk) == str(escolhido)),
        profissionais[0] if profissionais else None,
    )
    if practitioner is not None:
        request.session[SESSION_PRACTITIONER] = practitioner.pk
    clinic = request.clinic
    ver_rechamadas = can(request, Module.RECALLS, Action.VIEW)
    config = {
        "practitioner": practitioner.pk if practitioner else None,
        "start": clinic.schedule_start.strftime("%H:%M:%S"),
        "end": clinic.schedule_end.strftime("%H:%M:%S"),
        "intervalo": clinic.schedule_interval,
        "date": request.GET.get("date") or _remembered_date(request),
        # FullCalendar locale and the texts its script shows (badges in the day headers).
        "language": get_language(),
        # "Now" on the clinic's wall clock: the calendar runs in UTC mode (decision 117).
        "agora": _clock(timezone.now()),
        "textos": {
            "aniversariantes": _("aniversariante(s)"),
            "rechamadas": _("rechamada(s) pendente(s)"),
        },
        "pode": {acao: can(request, Module.SCHEDULE, acao) for acao in ("criar", "alterar")},
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
            "so_a_propria": own_schedule_only(request),
        },
    )


@requires_permission(Module.SCHEDULE, Action.VIEW)
def events(request):
    periodo = _range(request)
    practitioner = request.GET.get("practitioner", "")
    if periodo is None or not practitioner.isdecimal():
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start, end = periodo
    # The middle of the visible range falls inside the week (or month) on the screen.
    meio = timezone.localtime(start + (end - start) / 2).date()
    request.session[SESSION_DATE] = {
        "data": meio.isoformat(),
        "em": timezone.localdate().isoformat(),
    }
    agendamentos = (
        services.visible_appointments(request)
        .filter(practitioner_id=int(practitioner), start__lt=end, end__gt=start)
        .select_related("kind", "patient")
    )
    return JsonResponse(
        [
            {
                "id": appointment.pk,
                "title": appointment.title,
                "start": _clock(appointment.start),
                "end": _clock(appointment.end),
                "backgroundColor": appointment.kind.color,
                "borderColor": appointment.kind.color,
                "textColor": "#212529",
                "classNames": [f"status-{appointment.status}"],
                "extendedProps": {
                    "kind": appointment.kind.display_name,
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


@requires_permission(Module.SCHEDULE, Action.CREATE)
def new_appointment(request):
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
    form = AppointmentForm(
        request.POST or None,
        initial=inicial,
        instance=Appointment(),
        clinic=request.clinic,
        profissionais=services.visible_practitioners(request),
    )
    if request.method == "POST" and form.is_valid():
        try:
            criados = services.create(form.instance, form.intervalos, request.user)
        except IntegrityError:
            form.add_error(
                None, _("Outro agendamento acabou de ocupar este horário. Nada foi gravado.")
            )
        else:
            total = len(criados)
            return _success_response(
                ngettext("Agendamento criado.", "%(n)s agendamentos criados.", total) % {"n": total}
            )
    return render(request, "schedule/_form.html", {"form": form, "appointment": form.instance})


@requires_permission(Module.SCHEDULE, Action.CHANGE)
def edit_appointment(request, pk):
    appointment = get_object_or_404(
        services.visible_appointments(request).select_related("patient"), pk=pk
    )
    form = AppointmentForm(
        request.POST or None,
        instance=appointment,
        clinic=request.clinic,
        profissionais=services.visible_practitioners(request),
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
            return _success_response(_("Agendamento alterado."))
    return render(request, "schedule/_form.html", {"form": form, "appointment": appointment})


STATUS_MESSAGES = {
    Appointment.Status.BOOKED: gettext_lazy("%(nome)s: marcação de presença desfeita."),
    Appointment.Status.ATTENDED: gettext_lazy("%(nome)s compareceu."),
    Appointment.Status.MISSED: gettext_lazy("%(nome)s faltou."),
    Appointment.Status.CANCELLED: gettext_lazy("%(nome)s desmarcou. O horário ficou livre."),
}


@require_POST
@requires_permission(Module.SCHEDULE, Action.CHANGE)
def status(request, pk):
    """Came / missed / cancelled, from the appointment window or the home page."""
    appointment = get_object_or_404(
        services.visible_appointments(request).select_related("patient", "practitioner"), pk=pk
    )
    try:
        services.mark(appointment, request.POST.get("status", ""))
    except ValidationError as error:
        if request.headers.get("HX-Request"):
            # Back to the appointment window, with the reason.
            appointment.refresh_from_db()
            form = AppointmentForm(
                instance=appointment,
                clinic=request.clinic,
                profissionais=services.visible_practitioners(request),
            )
            context = {"form": form, "appointment": appointment, "erro_situacao": error.messages[0]}
            return render(request, "schedule/_form.html", context)
        messages.error(request, error.messages[0])
        return redirect("home")
    message = STATUS_MESSAGES[appointment.status] % {"nome": appointment.patient.name}
    if request.headers.get("HX-Request"):
        return _success_response(message)
    messages.success(request, message)
    return redirect("home")


@requires_permission(Module.SCHEDULE, Action.DELETE)
def delete_appointment(request, pk):
    appointment = get_object_or_404(
        services.visible_appointments(request).select_related("patient"), pk=pk
    )
    if request.method == "POST":
        excluidos = Appointment.objects.filter(pk=appointment.pk)
        if request.POST.get("escopo") == "serie" and appointment.series:
            # This one and the following ones of the same series.
            excluidos = Appointment.objects.filter(
                series=appointment.series, start__gte=appointment.start
            )
        total, _ = excluidos.delete()
        return _success_response(
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


def _birthdays_on(days):
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


@requires_permission(Module.SCHEDULE, Action.VIEW)
def birthdays(request):
    """Number of birthdays per day in the period shown by the calendar."""
    periodo = _range(request)
    if periodo is None:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start = timezone.localdate(periodo[0])
    total_dias = (timezone.localdate(periodo[1]) - start).days
    days = [start + datetime.timedelta(days=n) for n in range(total_dias)]
    return JsonResponse(
        {day.isoformat(): len(results) for day, results in _birthdays_on(days).items() if results}
    )


@requires_permission(Module.SCHEDULE, Action.VIEW)
def birthdays_on_day(request):
    try:
        day = datetime.date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return HttpResponse(_("Data inválida."), status=400)
    birthdays = [
        (patient, day.year - patient.birth_date.year) for patient in _birthdays_on([day])[day]
    ]
    return render(request, "schedule/_birthdays.html", {"dia": day, "aniversariantes": birthdays})
