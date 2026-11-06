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
    return render(request, "schedule/types.html", {"types": AppointmentType.objects.all()})


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
    remembered = request.session.get(SESSION_DATE) or {}
    today = timezone.localdate().isoformat()
    return remembered.get("data", "") if remembered.get("em") == today else ""


def _success_response(message):
    """Empty HTMX response that tells the page to close the modal and reload events."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps({"scheduleUpdated": {"message": message}})
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
    practitioners = list(services.visible_practitioners(request).filter(active=True))
    chosen_one = request.GET.get("practitioner") or request.session.get(SESSION_PRACTITIONER)
    practitioner = next(
        (p for p in practitioners if str(p.pk) == str(chosen_one)),
        practitioners[0] if practitioners else None,
    )
    if practitioner is not None:
        request.session[SESSION_PRACTITIONER] = practitioner.pk
    clinic = request.clinic
    can_see_recalls = can(request, Module.RECALLS, Action.VIEW)
    config = {
        "practitioner": practitioner.pk if practitioner else None,
        "start": clinic.schedule_start.strftime("%H:%M:%S"),
        "end": clinic.schedule_end.strftime("%H:%M:%S"),
        "interval": clinic.schedule_interval,
        "date": request.GET.get("date") or _remembered_date(request),
        # FullCalendar locale and the texts its script shows (badges in the day headers).
        "language": get_language(),
        # "Now" on the clinic's wall clock: the calendar runs in UTC mode (decision 117).
        "now": _clock(timezone.now()),
        "texts": {
            "birthdays": _("aniversariante(s)"),
            "recalls": _("rechamada(s) pendente(s)"),
        },
        "can": {
            "create": can(request, Module.SCHEDULE, Action.CREATE),
            "change": can(request, Module.SCHEDULE, Action.CHANGE),
        },
        "urls": {
            "events": reverse("schedule:events"),
            "new": reverse("schedule:new"),
            "birthdays": reverse("schedule:birthdays"),
            "birthdays_today": reverse("schedule:birthdays_today"),
            "recalls": reverse("recalls:summary") if can_see_recalls else None,
            "recalls_today": reverse("recalls:today") if can_see_recalls else None,
        },
    }
    return render(
        request,
        "schedule/calendar.html",
        {
            "practitioners": practitioners,
            "practitioner": practitioner,
            "types": AppointmentType.objects.filter(active=True),
            "schedule_settings": config,
            "own_only": own_schedule_only(request),
        },
    )


@requires_permission(Module.SCHEDULE, Action.VIEW)
def events(request):
    period = _range(request)
    practitioner = request.GET.get("practitioner", "")
    if period is None or not practitioner.isdecimal():
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start, end = period
    # The middle of the visible range falls inside the week (or month) on the screen; when the
    # range holds today, today: the day view, the first one on a phone, then opens on it.
    if start <= timezone.now() < end:
        remembered = timezone.localdate()
    else:
        remembered = timezone.localtime(start + (end - start) / 2).date()
    request.session[SESSION_DATE] = {
        "data": remembered.isoformat(),
        "em": timezone.localdate().isoformat(),
    }
    appointments = (
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
            for appointment in appointments
        ],
        safe=False,
    )


@requires_permission(Module.SCHEDULE, Action.CREATE)
def new_appointment(request):
    initial = {
        field: request.GET[parameter]
        for field, parameter in [
            ("practitioner", "practitioner"),
            ("date", "date"),
            ("start_time", "start"),
            ("end_time", "end"),
        ]
        if request.GET.get(parameter)
    }
    form = AppointmentForm(
        request.POST or None,
        initial=initial,
        instance=Appointment(),
        clinic=request.clinic,
        practitioners=services.visible_practitioners(request),
    )
    if request.method == "POST" and form.is_valid():
        try:
            created_count = services.create(form.instance, form.intervals, request.user)
        except IntegrityError:
            form.add_error(
                None, _("Outro agendamento acabou de ocupar este horário. Nada foi gravado.")
            )
        else:
            total = len(created_count)
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
        practitioners=services.visible_practitioners(request),
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
                practitioners=services.visible_practitioners(request),
            )
            context = {"form": form, "appointment": appointment, "status_error": error.messages[0]}
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
        excluded = Appointment.objects.filter(pk=appointment.pk)
        if request.POST.get("scope") == "serie" and appointment.series:
            # This one and the following ones of the same series.
            excluded = Appointment.objects.filter(
                series=appointment.series, start__gte=appointment.start
            )
        total, _ = excluded.delete()
        return _success_response(
            ngettext("Agendamento excluído.", "%(n)s agendamentos excluídos.", total) % {"n": total}
        )
    upcoming = 0
    if appointment.series:
        upcoming = Appointment.objects.filter(
            series=appointment.series, start__gt=appointment.start
        ).count()
    return render(
        request, "schedule/_delete.html", {"appointment": appointment, "following_count": upcoming}
    )


def _birthdays_on(days):
    """{date: [patients]} for active patients whose birthday falls on the given days."""
    query_filter = Q()
    for day in days:
        query_filter |= Q(birth_date__month=day.month, birth_date__day=day.day)
    result = {day: [] for day in days}
    if not days:
        return result
    patients = Patient.objects.filter(query_filter, active=True, archived=False).order_by("name")
    by_month_day = {(day.month, day.day): day for day in days}
    for patient in patients:
        birth_date = patient.birth_date
        result[by_month_day[(birth_date.month, birth_date.day)]].append(patient)
    return result


@requires_permission(Module.SCHEDULE, Action.VIEW)
def birthdays(request):
    """Number of birthdays per day in the period shown by the calendar."""
    period = _range(request)
    if period is None:
        return JsonResponse({"erro": _("Parâmetros inválidos.")}, status=400)
    start = timezone.localdate(period[0])
    total_days = (timezone.localdate(period[1]) - start).days
    days = [start + datetime.timedelta(days=n) for n in range(total_days)]
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
    return render(request, "schedule/_birthdays.html", {"day": day, "birthdays": birthdays})
