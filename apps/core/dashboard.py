"""Home page summary of the day (0.24.0).

Each block is built only when the user may see its module, so the front desk never gets
the clinic's expenses and a practitioner gets only their own schedule.
"""

import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from apps.estimates.models import Estimate
from apps.finance import services as finance_services
from apps.finance.models import ZERO, CashRegister, Entry, Installment
from apps.finance.payment_methods import labels as method_labels
from apps.patients.models import Patient
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment

from .permissions import Action, Module, can, own_schedule_only

# How many lines each list shows before the "see all" link.
LIMIT = 8
# Estimates whose validity ends within this many days.
ESTIMATE_DAYS = 7
PAYABLE_DAYS = 7


def build(request):
    today = timezone.localdate()
    panel = {"today": today}
    if can(request, Module.SCHEDULE, Action.VIEW):
        panel["schedule"] = _schedule(request, today)
    if can(request, Module.RECALLS, Action.VIEW):
        panel["recalls"] = _recalls(today)
    if can(request, Module.BIRTHDAYS, Action.VIEW):
        panel["birthdays"] = _birthdays(today)
    if can(request, Module.ESTIMATES, Action.VIEW):
        panel["estimates"] = _estimates(today)
    if can(request, Module.RECEIVING, Action.VIEW):
        panel["receipts"] = _receipts(today)
    if can(request, Module.FINANCE, Action.VIEW):
        panel["finance"] = _finance(today)
    return panel


def _schedule(request, today):
    now = timezone.now()
    visible = agenda.visible_appointments(request)
    of_the_day = list(
        visible.filter(start__date=today)
        .select_related("patient", "practitioner", "kind")
        .order_by("start", "practitioner__name")
    )
    patients = [a for a in of_the_day if a.patient_id]
    status = Appointment.Status
    counts = {value: 0 for value in status.values}
    for appointment in patients:
        counts[appointment.status] += 1
    pending = [a for a in patients if a.status == status.BOOKED]
    # No-show rate of the month so far, over the appointments someone marked.
    booked = dict(
        visible.filter(
            start__date__gte=today.replace(day=1),
            start__date__lte=today,
            status__in=[status.ATTENDED, status.MISSED],
        )
        .order_by()
        .values_list("status")
        .annotate(total=Count("pk"))
    )
    attended, missed = booked.get(status.ATTENDED, 0), booked.get(status.MISSED, 0)
    return {
        "items": of_the_day,
        # A practitioner sees only their own schedule, so the column would repeat their name.
        "show_practitioner": not own_schedule_only(request),
        "patients": len(patients) - counts[status.CANCELLED],
        "attended": counts[status.ATTENDED],
        "missed": counts[status.MISSED],
        "cancelled": counts[status.CANCELLED],
        "upcoming": sum(1 for a in pending if a.start > now),
        "unmarked": sum(1 for a in pending if a.start <= now),
        "next": next((a for a in pending if a.end > now), None),
        "now": now,
        "missed_pct_month": round(100 * missed / (attended + missed))
        if attended + missed
        else None,
        "booked_month": attended + missed,
    }


def _recalls(today):
    pending = Recall.objects.filter(
        done=False, date__lte=today, patient__archived=False
    ).select_related("patient")
    return {
        "items": list(pending.order_by("date", "patient__name")[:LIMIT]),
        "total": pending.count(),
        "late": pending.filter(date__lt=today).count(),
    }


def _birthdays(today):
    return [
        (patient, today.year - patient.birth_date.year)
        for patient in Patient.objects.filter(
            active=True,
            archived=False,
            birth_date__month=today.month,
            birth_date__day=today.day,
        ).order_by("name")
    ]


def _estimates(today):
    return list(
        Estimate.objects.filter(
            status=Estimate.Status.OPEN,
            valid_until__gte=today,
            valid_until__lte=today + datetime.timedelta(days=ESTIMATE_DAYS),
            patient__archived=False,
        )
        .select_related("patient")
        .prefetch_related("items")
        .order_by("valid_until", "patient__name")
    )


def _sum_of_balances(installments):
    balances = list(installments.values_list("balance", flat=True))
    return sum(balances, start=ZERO), len(balances)


def _receipts(today):
    received_payments = finance_services.valid_payments().filter(
        date=today, installment__entry__kind=Entry.Kind.RECEIVABLE
    )
    methods = method_labels()
    by_method = [
        (methods.get(method, method), total)
        for method, total in received_payments.order_by()
        .values_list("method")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    ]
    receivable, installments = _sum_of_balances(
        Installment.objects.unpaid().filter(entry__kind=Entry.Kind.RECEIVABLE, due_date=today)
    )
    return {
        "received": sum((total for _method, total in by_method), start=ZERO),
        "by_method": by_method,
        "receivable": receivable,
        "receivable_count": installments,
        "cash_registers": list(
            CashRegister.objects.filter(closed_at__isnull=True).select_related("account")
        ),
    }


def _finance(today):
    received_today, paid_today = finance_services.received_and_paid(today, today)
    month_start = today.replace(day=1)
    received_month, paid_month = finance_services.received_and_paid(month_start, today)
    # The same days of last month (up to its last day, for the 31st).
    previous_end = month_start - datetime.timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    ate_anterior = previous_start.replace(day=min(today.day, previous_end.day))
    received_previous, paid_previous = finance_services.received_and_paid(
        previous_start, ate_anterior
    )
    unpaid = Installment.objects.unpaid()
    overdue, overdue_installments = _sum_of_balances(
        unpaid.filter(entry__kind=Entry.Kind.RECEIVABLE, due_date__lt=today)
    )
    payable, payable_count = _sum_of_balances(
        unpaid.filter(
            entry__kind=Entry.Kind.PAYABLE,
            due_date__lte=today + datetime.timedelta(days=PAYABLE_DAYS),
        )
    )
    return {
        "paid_today": paid_today,
        "result_today": received_today - paid_today,
        "received_month": received_month,
        "paid_month": paid_month,
        "result_month": received_month - paid_month,
        "previous_result": received_previous - paid_previous,
        "previous_start": previous_start,
        "previous_until": ate_anterior,
        "overdue": overdue,
        "overdue_count": overdue_installments,
        "payable": payable,
        "payable_count": payable_count,
        "account_balances": sum(
            (balance for _account, balance in finance_services.account_balances()), start=ZERO
        ),
    }
