"""Scheduling rules: weekly recurrences and conflict detection."""

import datetime
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.permissions import own_schedule_only
from apps.practitioners.models import Practitioner

from .models import Appointment


def visible_practitioners(request):
    """Practitioners whose schedule the user may see and change (decision 044)."""
    if own_schedule_only(request):
        return Practitioner.objects.filter(user=request.user)
    return Practitioner.objects.all()


def visible_appointments(request):
    return Appointment.objects.filter(practitioner__in=visible_practitioners(request))


def timestamp(date, hour):
    """Aware datetime for a local date and time."""
    return timezone.make_aware(datetime.datetime.combine(date, hour))


def occurrences(date, start_time, end_time, repetitions=1):
    """(start, end) of each weekly occurrence, built from local date/time (DST-safe)."""
    return [
        (timestamp(day, start_time), timestamp(day, end_time))
        for day in (date + datetime.timedelta(weeks=week) for week in range(repetitions))
    ]


def conflicts(practitioner, intervals, ignore=None):
    """Existing appointments of the practitioner that overlap any of the intervals.

    Cancelled ones (desmarcados) do not hold the slot.
    """
    overlap = Q()
    for start, end in intervals:
        overlap |= Q(start__lt=end, end__gt=start)
    existing = Appointment.objects.filter(overlap, practitioner=practitioner).exclude(
        status=Appointment.Status.CANCELLED
    )
    if ignore is not None:
        existing = existing.exclude(pk=ignore)
    return list(existing.select_related("patient").order_by("start"))


@transaction.atomic
def create(model, intervals, user):
    """Create one appointment per interval, copying the fields of `modelo`.

    Raises IntegrityError if the database constraint finds an overlap (for example,
    another user booked the same slot a moment earlier); nothing is saved then.
    """
    series = uuid.uuid4() if len(intervals) > 1 else None
    created_count = []
    for start, end in intervals:
        appointment = Appointment(
            practitioner=model.practitioner,
            kind=model.kind,
            patient=model.patient,
            description=model.description,
            start=start,
            end=end,
            series=series,
            created_by=user,
        )
        appointment.save()
        created_count.append(appointment)
    return created_count


@transaction.atomic
def mark(appointment, status):
    """Record whether the patient came, missed or cancelled (0.24.0).

    Came or missed only from the day of the appointment on. Leaving "cancelled" takes the
    slot back, so it is refused if another appointment took it meanwhile.
    """
    if status not in Appointment.Status.values:
        raise ValidationError(_("Invalid status."))
    if appointment.patient_id is None:
        raise ValidationError(_("Only appointments with a patient have a status."))
    attendance = (Appointment.Status.ATTENDED, Appointment.Status.MISSED)
    if status in attendance and not appointment.attendance_markable:
        raise ValidationError(
            _("Came or missed can only be marked from the day of the appointment on.")
        )
    busy = _("This time slot has already been taken by another appointment. Cancel that one first.")
    if appointment.is_cancelled and status != Appointment.Status.CANCELLED:
        if conflicts(
            appointment.practitioner, [(appointment.start, appointment.end)], appointment.pk
        ):
            raise ValidationError(busy)
    appointment.status = status
    try:
        with transaction.atomic():
            appointment.save(update_fields=["status", "updated_at"])
    except IntegrityError:
        raise ValidationError(busy) from None
    return appointment
