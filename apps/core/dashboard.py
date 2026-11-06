"""Home page summary of the day (0.24.0).

Each block is built only when the user may see its module, so the front desk never gets
the clinic's expenses and a practitioner gets only their own schedule.
"""

import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from apps.estimates.models import Estimate
from apps.finance import services as financeiro
from apps.finance.models import ZERO, CashRegister, Entry, Installment
from apps.finance.payment_methods import labels as rotulos_das_formas
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
    painel = {"today": today}
    if can(request, Module.SCHEDULE, Action.VIEW):
        painel["schedule"] = _schedule(request, today)
    if can(request, Module.RECALLS, Action.VIEW):
        painel["recalls"] = _recalls(today)
    if can(request, Module.BIRTHDAYS, Action.VIEW):
        painel["birthdays"] = _birthdays(today)
    if can(request, Module.ESTIMATES, Action.VIEW):
        painel["estimates"] = _estimates(today)
    if can(request, Module.RECEIVING, Action.VIEW):
        painel["receipts"] = _receipts(today)
    if can(request, Module.FINANCE, Action.VIEW):
        painel["finance"] = _finance(today)
    return painel


def _schedule(request, today):
    now = timezone.now()
    visible = agenda.visible_appointments(request)
    do_dia = list(
        visible.filter(start__date=today)
        .select_related("patient", "practitioner", "kind")
        .order_by("start", "practitioner__name")
    )
    pacientes = [a for a in do_dia if a.patient_id]
    status = Appointment.Status
    contagem = {value: 0 for value in status.values}
    for appointment in pacientes:
        contagem[appointment.status] += 1
    pendentes = [a for a in pacientes if a.status == status.BOOKED]
    # No-show rate of the month so far, over the appointments someone marked.
    marcados = dict(
        visible.filter(
            start__date__gte=today.replace(day=1),
            start__date__lte=today,
            status__in=[status.ATTENDED, status.MISSED],
        )
        .order_by()
        .values_list("status")
        .annotate(total=Count("pk"))
    )
    vieram, faltaram = marcados.get(status.ATTENDED, 0), marcados.get(status.MISSED, 0)
    return {
        "items": do_dia,
        # A practitioner sees only their own schedule, so the column would repeat their name.
        "show_practitioner": not own_schedule_only(request),
        "patients": len(pacientes) - contagem[status.CANCELLED],
        "attended": contagem[status.ATTENDED],
        "missed": contagem[status.MISSED],
        "cancelled": contagem[status.CANCELLED],
        "upcoming": sum(1 for a in pendentes if a.start > now),
        "unmarked": sum(1 for a in pendentes if a.start <= now),
        "next": next((a for a in pendentes if a.end > now), None),
        "now": now,
        "missed_pct_month": round(100 * faltaram / (vieram + faltaram))
        if vieram + faltaram
        else None,
        "booked_month": vieram + faltaram,
    }


def _recalls(today):
    pendentes = Recall.objects.filter(
        done=False, date__lte=today, patient__archived=False
    ).select_related("patient")
    return {
        "items": list(pendentes.order_by("date", "patient__name")[:LIMIT]),
        "total": pendentes.count(),
        "late": pendentes.filter(date__lt=today).count(),
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


def _sum_of_balances(parcelas):
    saldos = list(parcelas.values_list("balance", flat=True))
    return sum(saldos, start=ZERO), len(saldos)


def _receipts(today):
    recebidos = financeiro.valid_payments().filter(
        date=today, installment__entry__kind=Entry.Kind.RECEIVABLE
    )
    formas = rotulos_das_formas()
    por_forma = [
        (formas.get(method, method), total)
        for method, total in recebidos.order_by()
        .values_list("method")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    ]
    a_receber, parcelas = _sum_of_balances(
        Installment.objects.unpaid().filter(entry__kind=Entry.Kind.RECEIVABLE, due_date=today)
    )
    return {
        "received": sum((total for _forma, total in por_forma), start=ZERO),
        "by_method": por_forma,
        "receivable": a_receber,
        "receivable_count": parcelas,
        "cash_registers": list(
            CashRegister.objects.filter(closed_at__isnull=True).select_related("account")
        ),
    }


def _finance(today):
    recebido_hoje, pago_hoje = financeiro.received_and_paid(today, today)
    inicio_mes = today.replace(day=1)
    recebido_mes, pago_mes = financeiro.received_and_paid(inicio_mes, today)
    # The same days of last month (up to its last day, for the 31st).
    fim_anterior = inicio_mes - datetime.timedelta(days=1)
    inicio_anterior = fim_anterior.replace(day=1)
    ate_anterior = inicio_anterior.replace(day=min(today.day, fim_anterior.day))
    recebido_anterior, pago_anterior = financeiro.received_and_paid(inicio_anterior, ate_anterior)
    abertas = Installment.objects.unpaid()
    vencido, parcelas_vencidas = _sum_of_balances(
        abertas.filter(entry__kind=Entry.Kind.RECEIVABLE, due_date__lt=today)
    )
    a_pagar, contas_a_pagar = _sum_of_balances(
        abertas.filter(
            entry__kind=Entry.Kind.PAYABLE,
            due_date__lte=today + datetime.timedelta(days=PAYABLE_DAYS),
        )
    )
    return {
        "paid_today": pago_hoje,
        "result_today": recebido_hoje - pago_hoje,
        "received_month": recebido_mes,
        "paid_month": pago_mes,
        "result_month": recebido_mes - pago_mes,
        "previous_result": recebido_anterior - pago_anterior,
        "previous_start": inicio_anterior,
        "previous_until": ate_anterior,
        "overdue": vencido,
        "overdue_count": parcelas_vencidas,
        "payable": a_pagar,
        "payable_count": contas_a_pagar,
        "account_balances": sum(
            (saldo for _account, saldo in financeiro.account_balances()), start=ZERO
        ),
    }
