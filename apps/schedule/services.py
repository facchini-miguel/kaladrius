"""Scheduling rules: weekly recurrences and conflict detection."""

import datetime
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.permissions import so_a_propria_agenda
from apps.practitioners.models import Practitioner

from .models import Appointment


def profissionais_visiveis(request):
    """Practitioners whose schedule the user may see and change (decision 044)."""
    if so_a_propria_agenda(request):
        return Practitioner.objects.filter(user=request.user)
    return Practitioner.objects.all()


def agendamentos_visiveis(request):
    return Appointment.objects.filter(practitioner__in=profissionais_visiveis(request))


def timestamp(date, hour):
    """Aware datetime for a local date and time."""
    return timezone.make_aware(datetime.datetime.combine(date, hour))


def ocorrencias(date, start_time, end_time, repeticoes=1):
    """(start, end) of each weekly occurrence, built from local date/time (DST-safe)."""
    return [
        (timestamp(day, start_time), timestamp(day, end_time))
        for day in (date + datetime.timedelta(weeks=week) for week in range(repeticoes))
    ]


def conflitos(practitioner, intervalos, ignorar=None):
    """Existing appointments of the practitioner that overlap any of the intervals.

    Cancelled ones (desmarcados) do not hold the slot.
    """
    sobreposicao = Q()
    for start, end in intervalos:
        sobreposicao |= Q(start__lt=end, end__gt=start)
    existentes = Appointment.objects.filter(sobreposicao, practitioner=practitioner).exclude(
        status=Appointment.Situacao.DESMARCOU
    )
    if ignorar is not None:
        existentes = existentes.exclude(pk=ignorar)
    return list(existentes.select_related("patient").order_by("start"))


@transaction.atomic
def criar(modelo, intervalos, user):
    """Create one appointment per interval, copying the fields of `modelo`.

    Raises IntegrityError if the database constraint finds an overlap (for example,
    another user booked the same slot a moment earlier); nothing is saved then.
    """
    series = uuid.uuid4() if len(intervalos) > 1 else None
    criados = []
    for start, end in intervalos:
        appointment = Appointment(
            practitioner=modelo.practitioner,
            kind=modelo.kind,
            patient=modelo.patient,
            description=modelo.description,
            start=start,
            end=end,
            series=series,
            created_by=user,
        )
        appointment.save()
        criados.append(appointment)
    return criados


@transaction.atomic
def marcar(appointment, status):
    """Record whether the patient came, missed or cancelled (0.24.0).

    Came or missed only from the day of the appointment on. Leaving "cancelled" takes the
    slot back, so it is refused if another appointment took it meanwhile.
    """
    if status not in Appointment.Situacao.values:
        raise ValidationError(_("Situação inválida."))
    if appointment.patient_id is None:
        raise ValidationError(_("Só agendamentos com paciente têm situação."))
    presenca = (Appointment.Situacao.COMPARECEU, Appointment.Situacao.FALTOU)
    if status in presenca and not appointment.presenca_marcavel:
        raise ValidationError(
            _("Comparecimento e falta só podem ser marcados a partir do dia do atendimento.")
        )
    ocupado = _("Este horário já foi ocupado por outro agendamento. Desmarque aquele antes.")
    if appointment.desmarcado and status != Appointment.Situacao.DESMARCOU:
        if conflitos(
            appointment.practitioner, [(appointment.start, appointment.end)], appointment.pk
        ):
            raise ValidationError(ocupado)
    appointment.status = status
    try:
        with transaction.atomic():
            appointment.save(update_fields=["status", "updated_at"])
    except IntegrityError:
        raise ValidationError(ocupado) from None
    return appointment
