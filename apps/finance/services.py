"""Financial rules: installments, receiving, reversing, cancelling and debtors."""

import calendar
import datetime
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import pgettext

from apps.core.models import Clinic
from apps.core.ordering import alphabetical_key

from . import commissions
from .models import (
    ZERO,
    AccountGroup,
    BankTransaction,
    BookClosing,
    CashMovement,
    CashRegister,
    Category,
    Commission,
    CostCenter,
    Entry,
    Installment,
    Payment,
    Planning,
)
from .payment_methods import labels as rotulos_das_formas

CENT = Decimal("0.01")
MONEY = DecimalField(max_digits=12, decimal_places=2)
# Days overdue for the debtors report: up to 30, 31-60, 61-90, over 90.
OVERDUE_BRACKETS = [30, 60, 90]


def split(total, quantity):
    """Equal installments; the leftover cents go to the first one."""
    base = (total / quantity).quantize(CENT, rounding=ROUND_DOWN)
    paid_and_balance = [base] * quantity
    paid_and_balance[0] += total - base * quantity
    return paid_and_balance


def add_months(date, meses):
    """Same day N months later (the 31st becomes the last day of shorter months)."""
    year, month = divmod(date.month - 1 + meses, 12)
    year, month = date.year + year, month + 1
    return date.replace(
        year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1])
    )


@transaction.atomic
def create_entry(*, parcelas, primeiro_vencimento, user, **fields):
    """Create an entry with `parcelas` monthly installments from `primeiro_vencimento`."""
    entry = Entry.objects.create(created_by=user, **fields)
    # One by one (at most 48), not bulk_create, so the audit log records each installment.
    for number, amount in enumerate(split(entry.total_amount, parcelas), start=1):
        Installment.objects.create(
            clinic=entry.clinic,
            entry=entry,
            number=number,
            due_date=add_months(primeiro_vencimento, number - 1),
            amount=amount,
        )
    return entry


@transaction.atomic
def receive(installment, *, user, **fields):
    """Record a payment for an installment. Raises ValidationError if it exceeds the balance.

    The installment row is locked, so two people receiving at once cannot overpay it.
    """
    installment = (
        Installment.objects.select_for_update().select_related("entry").get(pk=installment.pk)
    )
    if installment.entry.cancelled:
        raise ValidationError(_("Este lançamento foi cancelado."))
    payment = Payment(clinic=installment.clinic, installment=installment, created_by=user, **fields)
    check_period(payment.clinic_id, payment.date)
    _pago, balance = installment.paid_and_balance()
    if payment.principal <= 0:
        raise ValidationError(_("O valor abatido da parcela precisa ser maior que zero."))
    if payment.principal > balance:
        raise ValidationError(
            _("O valor abatido (%(abatido)s) passa do que falta na parcela (%(saldo)s).")
            % {"abatido": payment.principal, "saldo": balance}
        )
    payment.save()
    return payment


@transaction.atomic
def reverse_payment(payment, *, reason, user):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.reversed:
        raise ValidationError(_("Este pagamento já foi estornado."))
    check_period(payment.clinic_id, payment.date)
    payment.reversed = True
    payment.reversed_at = timezone.now()
    payment.reversed_by = user
    payment.reversal_reason = reason
    # Only these fields: the commission links are set elsewhere and must not be overwritten.
    payment.save(update_fields=["reversed", "reversed_at", "reversed_by", "reversal_reason"])
    # A reversed payment no longer explains its bank statement line (saved, not .update(),
    # so the audit log records it).
    for transacao in BankTransaction.objects.filter(payment=payment):
        transacao.payment = None
        transacao.status = BankTransaction.Status.PENDING
        transacao.reconciled_by = None
        transacao.reconciled_at = None
        transacao.save()
    return payment


@transaction.atomic
def cancel(entry, *, reason, user):
    """Cancel an entry. Payments must be reversed first (they are real money).

    The entry row is locked: receber() locks it too (through its installment), so a
    payment cannot be recorded while the entry is being cancelled.
    """
    entry = Entry.objects.select_for_update().get(pk=entry.pk)
    if entry.cancelled:
        raise ValidationError(_("Este lançamento já foi cancelado."))
    if Payment.objects.filter(installment__entry=entry, reversed=False).exists():
        raise ValidationError(
            _("Este lançamento tem pagamentos. Estorne os pagamentos antes de cancelar.")
        )
    commission = Commission.objects.filter(entry=entry, cancelled=False).first()
    if commission is not None:
        commissions.release(commission)  # raises ValidationError when it cannot be undone
    entry.cancelled = True
    entry.cancelled_at = timezone.now()
    entry.cancelled_by = user
    entry.cancellation_reason = reason
    entry.save()
    return entry


# --- Closing the books (decision 096) -------------------------------------------------


def closed_until(clinic_id):
    """Last day of the clinic's closed period, or None. Explicit clinic: also called by
    commands that run without the request's isolation."""
    last = BookClosing.all_objects.filter(clinic_id=clinic_id).first()  # newest first
    return last.until if last else None


def check_period(clinic_id, date):
    """Refuse money dated inside the closed period. Locks the clinic row, shared with
    fechar(), so a payment cannot slip in while the period is being closed."""
    Clinic.objects.select_for_update().get(pk=clinic_id)
    until = closed_until(clinic_id)
    if until is not None and date <= until:
        raise ValidationError(
            _(
                "O financeiro está fechado até %(ate)s: pagamentos e estornos nessa data ou "
                "antes dela não podem ser registrados. Use uma data posterior ou peça ao "
                "administrador para reabrir o período."
            )
            % {"ate": date_format(until, "SHORT_DATE_FORMAT")}
        )


@transaction.atomic
def close_books(clinic, until, *, user):
    """Close the books up to `ate` (at most yesterday: today's cash is still moving)."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    if until >= timezone.localdate():
        raise ValidationError(_("Feche no máximo até ontem: hoje ainda há movimento."))
    current = closed_until(clinic.pk)
    if current is not None and until <= current:
        raise ValidationError(
            _("O financeiro já está fechado até %(ate)s. Para voltar, reabra o período.")
            % {"ate": date_format(current, "SHORT_DATE_FORMAT")}
        )
    return BookClosing.objects.create(clinic=clinic, until=until, created_by=user)


@transaction.atomic
def reopen_books(clinic, until, *, reason, user):
    """Move the closing back to `ate` (None opens everything). A reason is required."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    current = closed_until(clinic.pk)
    if current is None:
        raise ValidationError(_("O financeiro não está fechado."))
    if until is not None and until >= current:
        raise ValidationError(_("Para reabrir, escolha uma data anterior ao fechamento atual."))
    if not reason.strip():
        raise ValidationError(_("Informe o motivo da reabertura."))
    return BookClosing.objects.create(
        clinic=clinic, until=until, reason=reason.strip(), created_by=user
    )


def status(installment, today=None):
    """Status of an installment annotated with com_saldo() (code, label)."""
    today = today or timezone.localdate()
    if installment.entry.cancelled:
        return "cancelada", _("Cancelada")
    if installment.balance <= 0:
        return "paga", _("Paga")
    if installment.due_date < today:
        return "vencida", _("Vencida")
    if installment.paid > 0:
        return "parcial", _("Paga em parte")
    return "aberta", pgettext("parcela", "Em aberto")


def debtors(today=None):
    """Who owes the clinic, from the open installments of receivables.

    One row per patient (or payer name): overdue total split by days late, amount not yet
    due and the oldest due date, ordered by the overdue total.
    """
    today = today or timezone.localdate()
    # Plain values, not model instances: a clinic with years of use has thousands of open
    # installments, and full objects took tens of MB per request (volume test, decision 108).
    parcelas = (
        Installment.objects.unpaid()
        .filter(entry__kind=Entry.Kind.RECEIVABLE)
        .values(
            "due_date",
            "balance",
            "entry__patient_id",
            "entry__patient__name",
            "entry__payer",
        )
    )
    rows = defaultdict(
        lambda: {
            "patient_id": None,
            "name": "",
            "brackets": [ZERO] * (len(OVERDUE_BRACKETS) + 1),
            "overdue": ZERO,
            "not_yet_due": ZERO,
            "oldest": None,
        }
    )
    for installment in parcelas:
        patient_id = installment["entry__patient_id"]
        payer = installment["entry__payer"]
        key = ("patient", patient_id) if patient_id else ("payer", payer.strip().lower())
        row = rows[key]
        row["patient_id"] = patient_id
        row["name"] = installment["entry__patient__name"] if patient_id else payer
        due_date, balance = installment["due_date"], installment["balance"]
        if due_date >= today:
            row["not_yet_due"] += balance
            continue
        atraso = (today - due_date).days
        faixa = next(
            (i for i, limit in enumerate(OVERDUE_BRACKETS) if atraso <= limit),
            len(OVERDUE_BRACKETS),
        )
        row["brackets"][faixa] += balance
        row["overdue"] += balance
        if row["oldest"] is None or due_date < row["oldest"]:
            row["oldest"] = due_date
    resultado = [row for row in rows.values() if row["overdue"] or row["not_yet_due"]]
    return sorted(resultado, key=lambda row: (-row["overdue"], alphabetical_key(row["name"])))


def patient_summary(patient, today=None):
    """Open installments, totals and latest payments of a patient (for the record)."""
    today = today or timezone.localdate()
    unpaid = list(
        Installment.objects.unpaid()
        .filter(entry__patient=patient, entry__kind=Entry.Kind.RECEIVABLE)
        .select_related("entry")
        .order_by("due_date")
    )
    return {
        "unpaid": unpaid,
        "overdue": sum((p.balance for p in unpaid if p.due_date < today), start=ZERO),
        "not_yet_due": sum((p.balance for p in unpaid if p.due_date >= today), start=ZERO),
        "payments": list(
            Payment.objects.filter(installment__entry__patient=patient)
            .select_related("installment__entry", "account")
            .order_by("-date", "-pk")[:5]
        ),
    }


# --- Cash flow and reports (0.16.0) ------------------------------------------------------


def _sign(kind):
    """Receivables bring money in (+), payables take it out (-)."""
    return 1 if kind == Entry.Kind.RECEIVABLE else -1


def valid_payments():
    return Payment.objects.filter(reversed=False, installment__entry__cancelled=False)


def account_balances(until=None):
    """[(account, balance)] = initial balance + money in - money out (payments up to `ate`).

    Summed in the database, grouped by account, so it does not grow with the history.
    """
    from .models import FinancialAccount

    pagamentos = valid_payments()
    if until is not None:
        pagamentos = pagamentos.filter(date__lte=until)
    cash_movement = defaultdict(lambda: ZERO)
    for account_id, kind, total in (
        pagamentos.order_by()
        .values_list("account_id", "installment__entry__kind")
        .annotate(total=Sum("amount"))
    ):
        cash_movement[account_id] += _sign(kind) * total
    movimentos = CashMovement.objects.all()
    if until is not None:
        movimentos = movimentos.filter(created_at__date__lte=until)
    for account_id, outra_id, kind, total in (
        movimentos.order_by()
        .values_list("cash_register__account_id", "other_account_id", "kind")
        .annotate(total=Sum("amount"))
    ):
        # A withdrawal leaves the drawer (into the other account, if any); a top-up enters it.
        sinal = -1 if kind == CashMovement.Kind.WITHDRAWAL else 1
        cash_movement[account_id] += sinal * total
        if outra_id:
            cash_movement[outra_id] -= sinal * total
    return [
        (account, account.opening_balance + cash_movement[account.pk])
        for account in FinancialAccount.objects.all().order_by("name")
    ]


def cash_flow(since, until, por_mes=False, today=None):
    """Rows per day (or month) from `de` to `ate`.

    Actual = payments made (by payment date); expected = what is still open in the
    installments due in the period (overdue ones included, flagged by the date). The
    running balance starts from the accounts' balance on the day before `de` and adds both.
    """
    today = today or timezone.localdate()

    def key(date):
        return date.replace(day=1) if por_mes else date

    rows = defaultdict(
        lambda: {
            "incoming": ZERO,
            "outgoing": ZERO,
            "expected_incoming": ZERO,
            "expected_outgoing": ZERO,
        }
    )
    for date, kind, amount in (
        valid_payments()
        .filter(date__gte=since, date__lte=until)
        .values_list("date", "installment__entry__kind", "amount")
    ):
        rows[key(date)]["incoming" if kind == Entry.Kind.RECEIVABLE else "outgoing"] += amount
    # Drawer movements to or from outside the system (moves between accounts net to zero).
    for timestamp, kind, amount in CashMovement.objects.filter(
        other_account__isnull=True, created_at__date__gte=since, created_at__date__lte=until
    ).values_list("created_at", "kind", "amount"):
        date = timezone.localtime(timestamp).date()
        rows[key(date)]["outgoing" if kind == CashMovement.Kind.WITHDRAWAL else "incoming"] += (
            amount
        )
    for installment in (
        Installment.objects.unpaid()
        .filter(due_date__gte=since, due_date__lte=until)
        .select_related("entry")
    ):
        field = (
            "expected_incoming"
            if installment.entry.kind == Entry.Kind.RECEIVABLE
            else "expected_outgoing"
        )
        rows[key(installment.due_date)][field] += installment.balance

    previous = since - datetime.timedelta(days=1)
    opening_balance = sum(
        (amount for _account, amount in account_balances(until=previous)), start=ZERO
    )
    balance = opening_balance
    resultado = []
    for date in sorted(rows):
        row = rows[date]
        row["date"] = date
        row["late"] = (
            not por_mes and date < today and (row["expected_incoming"] or row["expected_outgoing"])
        )
        balance += (
            row["incoming"] - row["outgoing"] + row["expected_incoming"] - row["expected_outgoing"]
        )
        row["balance"] = balance
        resultado.append(row)
    totais = {
        field: sum((row[field] for row in resultado), start=ZERO)
        for field in ("incoming", "outgoing", "expected_incoming", "expected_outgoing")
    }
    return {
        "rows": resultado,
        "totals": totais,
        "opening_balance": opening_balance,
        "closing_balance": balance,
    }


def received_and_paid(since, until):
    """(money received, money paid) from `de` to `ate`, in one query (home page, 0.24.0)."""
    totais = dict(
        valid_payments()
        .filter(date__gte=since, date__lte=until)
        .order_by()
        .values_list("installment__entry__kind")
        .annotate(total=Sum("amount"))
    )
    return totais.get(Entry.Kind.RECEIVABLE, ZERO), totais.get(Entry.Kind.PAYABLE, ZERO)


def report(since, until):
    """Money received and paid in the period, grouped for the reports page."""
    pagamentos = valid_payments().filter(date__gte=since, date__lte=until)
    recebidos = pagamentos.filter(installment__entry__kind=Entry.Kind.RECEIVABLE)
    pagos = pagamentos.filter(installment__entry__kind=Entry.Kind.PAYABLE)

    def agrupar(consulta, field, label=None):
        grupos = consulta.order_by().values_list(field).annotate(total=Sum("amount"))
        rows = [((label or {}).get(key, key), total) for key, total in grupos]
        return sorted(rows, key=lambda row: -row[1])

    def somar(consulta, field):
        return consulta.aggregate(total=Coalesce(Sum(field), ZERO, output_field=MONEY))["total"]

    formas = rotulos_das_formas()
    total_recebido = somar(recebidos, "amount")
    total_pago = somar(pagos, "amount")
    # The chart of accounts (decision 097) only once the clinic has groups.
    grupos = AccountGroup.objects.exists()
    # Cost centers (decision 095) only once the clinic has registered one.
    centros = CostCenter.objects.exists()
    sem_centro = {None: _("Sem centro de custo")}
    centro = "installment__entry__cost_center__name"
    return {
        "groups": grupos,
        "by_group": tree_by_group(recebidos, Category.Kind.INCOME) if grupos else [],
        "expenses_by_group": tree_by_group(pagos, Category.Kind.EXPENSE) if grupos else [],
        "centers": centros,
        "by_center": agrupar(recebidos, centro, sem_centro) if centros else [],
        "expenses_by_center": agrupar(pagos, centro, sem_centro) if centros else [],
        "by_method": agrupar(recebidos, "method", formas),
        "by_category": agrupar(recebidos, "installment__entry__category__name"),
        "by_practitioner": agrupar(recebidos, "installment__entry__practitioner__name"),
        "expenses_by_category": agrupar(pagos, "installment__entry__category__name"),
        "total_received": total_recebido,
        "total_paid": total_pago,
        "result": total_recebido - total_pago,
        "discounts": somar(recebidos, "discount"),
        "interest": somar(recebidos, "interest"),
    }


def link_groups(consulta):
    """The groups with each parent set from the same list, so numbers like 2.1 are
    built without one query per level."""
    grupos = list(consulta)
    por_id = {group.pk: group for group in grupos}
    for group in grupos:
        if group.parent_id in por_id:
            group.parent = por_id[group.parent_id]
    return grupos


def in_tree_order(grupos):
    """(level, group) pairs in chart order: each group followed by its subgroups."""
    filhos = defaultdict(list)
    for group in grupos:  # already in chart order (code, then name)
        filhos[group.parent_id].append(group)
    saida = []

    def descer(parent_id, nivel):
        for group in filhos[parent_id]:
            saida.append((nivel, group))
            descer(group.pk, nivel + 1)

    descer(None, 0)
    return saida


def totals_by_group(pagamentos, kind):
    """Payments summed by group, each group including its subgroups.

    Returns (groups of the type, {group id: total}, total of categories outside any group).
    """
    por_categoria = dict(
        pagamentos.order_by()
        .values_list("installment__entry__category_id")
        .annotate(total=Sum("amount"))
    )
    grupo_da_categoria = dict(Category.objects.filter(kind=kind).values_list("pk", "group_id"))
    grupos = link_groups(AccountGroup.objects.filter(kind=kind))
    parent = {group.pk: group.parent_id for group in grupos}
    totais = defaultdict(lambda: ZERO)
    sem_grupo = ZERO
    for category_id, amount in por_categoria.items():
        group_id = grupo_da_categoria.get(category_id)
        if group_id is None:
            sem_grupo += amount
        while group_id is not None:
            totais[group_id] += amount
            group_id = parent.get(group_id)
    return grupos, totais, sem_grupo


def tree_by_group(pagamentos, kind):
    """(level, name, total) rows in tree order for the reports, groups without money left
    out, and a last row for the categories outside any group."""
    grupos, totais, sem_grupo = totals_by_group(pagamentos, kind)
    rows = [
        (nivel, str(group), totais[group.pk])
        for nivel, group in in_tree_order(grupos)
        if totais[group.pk]
    ]
    if sem_grupo:
        rows.append((0, _("Sem grupo"), sem_grupo))
    return rows


# --- Yearly planning (decision 098) ---------------------------------------------------


def year_fraction(year, today=None):
    """Share of the year already gone: 0 before it starts, 1 once it is over."""
    today = today or timezone.localdate()
    start, end = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    if today < start:
        return Decimal(0)
    if today >= end:
        return Decimal(1)
    return Decimal((today - start).days + 1) / Decimal((end - start).days + 1)


def planning(year, today=None):
    """Goals of the year next to what was received and paid, group by group.

    "Esperado" is the goal times the share of the year gone, so mid-year a group can be
    compared with where it should be. Section totals add the goals of the highest groups
    that have one, so a goal and its subgroups' goals are not counted twice.
    """
    fracao = year_fraction(year, today)
    metas = dict(Planning.objects.filter(year=year).values_list("group_id", "amount"))
    pagamentos = valid_payments().filter(date__year=year)
    secoes = []
    for kind, label, lancamentos in (
        (Category.Kind.INCOME, _("Receitas"), Entry.Kind.RECEIVABLE),
        (Category.Kind.EXPENSE, _("Despesas"), Entry.Kind.PAYABLE),
    ):
        grupos, totais, sem_grupo = totals_by_group(
            pagamentos.filter(installment__entry__kind=lancamentos), kind
        )
        rows, meta_total, cobertos = [], ZERO, set()
        for nivel, group in in_tree_order(grupos):
            meta, realizado = metas.get(group.pk), totais[group.pk]
            if not group.active and meta is None and not realizado:
                continue
            if meta and group.parent_id not in cobertos:
                meta_total += meta
            if meta or group.parent_id in cobertos:
                cobertos.add(group.pk)
            esperado = (meta * fracao).quantize(CENT) if meta else None
            rows.append(
                {
                    "level": nivel,
                    "group": group,
                    "target": meta,
                    "actual": realizado,
                    "expected": esperado,
                    "percentage": round(100 * realizado / meta) if meta else None,
                    # On track: income at or above where it should be, expenses at or below.
                    "on_track": None
                    if not meta
                    else realizado >= esperado
                    if kind == Category.Kind.INCOME
                    else realizado <= esperado,
                }
            )
        realizado_total = (
            sum((totais[g.pk] for g in grupos if g.parent_id is None), ZERO) + sem_grupo
        )
        secoes.append(
            {
                "kind": kind,
                "label": label,
                "rows": rows,
                "ungrouped": sem_grupo,
                "target": meta_total,
                "expected": (meta_total * fracao).quantize(CENT),
                "actual": realizado_total,
            }
        )
    return {"year": year, "fraction": fracao, "sections": secoes}


@transaction.atomic
def save_targets(year, paid_and_balance):
    """{group: goal or None}: saves the goals, removing the ones left blank."""
    for group, amount in paid_and_balance.items():
        if amount:
            Planning.objects.update_or_create(year=year, group=group, defaults={"amount": amount})
        else:
            Planning.objects.filter(year=year, group=group).delete()


@transaction.atomic
def copy_targets(year):
    """Copy last year's goals into the groups still without a goal; returns how many."""
    existentes = set(Planning.objects.filter(year=year).values_list("group_id", flat=True))
    copiadas = 0
    for previous in Planning.objects.filter(year=year - 1).exclude(group_id__in=existentes):
        # One by one, not bulk_create, so the audit log records each goal.
        Planning.objects.create(year=year, group_id=previous.group_id, amount=previous.amount)
        copiadas += 1
    return copiadas


# --- Daily cash drawer (0.17.0) ----------------------------------------------------------


def open_cash_register(account):
    return CashRegister.objects.filter(account=account, closed_at__isnull=True).first()


@transaction.atomic
def open_register(account, *, amount, user):
    if open_cash_register(account) is not None:
        raise ValidationError(_("O caixa desta conta já está aberto."))
    return CashRegister.objects.create(
        clinic=account.clinic, account=account, opening_amount=amount, opened_by=user
    )


def register_summary(cash_register):
    """Money that went through the drawer since it was opened, and the expected amount.

    Payments count by the moment they were registered (not their date), so a payment
    typed in today for last week still lands in today's drawer.
    """
    end = cash_register.closed_at or timezone.now()
    pagamentos = list(
        valid_payments()
        .filter(
            account=cash_register.account,
            created_at__gte=cash_register.opened_at,
            created_at__lte=end,
        )
        .select_related("installment__entry__patient")
        .order_by("created_at")
    )
    movimentos = list(cash_register.movements.select_related("other_account", "created_by"))
    entradas = sum(
        (p.amount for p in pagamentos if p.installment.entry.kind == Entry.Kind.RECEIVABLE),
        start=ZERO,
    )
    saidas = sum(
        (p.amount for p in pagamentos if p.installment.entry.kind == Entry.Kind.PAYABLE),
        start=ZERO,
    )
    reforcos = sum((m.amount for m in movimentos if m.kind == CashMovement.Kind.TOP_UP), start=ZERO)
    retiradas = sum(
        (m.amount for m in movimentos if m.kind == CashMovement.Kind.WITHDRAWAL), start=ZERO
    )
    return {
        "payments": pagamentos,
        "movements": movimentos,
        "incoming": entradas,
        "outgoing": saidas,
        "top_ups": reforcos,
        "withdrawals": retiradas,
        "expected": cash_register.opening_amount + entradas - saidas + reforcos - retiradas,
    }


@transaction.atomic
def move_cash(cash_register, *, kind, amount, reason, user, other_account=None):
    cash_register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
    if not cash_register.is_open:
        raise ValidationError(_("Este caixa já foi fechado."))
    if other_account is not None and other_account.pk == cash_register.account_id:
        raise ValidationError(_("Escolha uma conta diferente da do caixa."))
    if (
        kind == CashMovement.Kind.WITHDRAWAL
        and amount > register_summary(cash_register)["expected"]
    ):
        raise ValidationError(_("A retirada passa do valor que deveria estar no caixa."))
    return CashMovement.objects.create(
        clinic=cash_register.clinic,
        cash_register=cash_register,
        kind=kind,
        amount=amount,
        reason=reason,
        other_account=other_account,
        created_by=user,
    )


@transaction.atomic
def close_register(cash_register, *, counted_amount, note, user):
    cash_register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
    if not cash_register.is_open:
        raise ValidationError(_("Este caixa já foi fechado."))
    cash_register.expected_amount = register_summary(cash_register)["expected"]
    cash_register.counted_amount = counted_amount
    cash_register.note = note
    cash_register.closed_at = timezone.now()
    cash_register.closed_by = user
    cash_register.save()
    return cash_register
