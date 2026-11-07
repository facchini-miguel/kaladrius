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
from .payment_methods import labels as method_labels

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


def add_months(date, months):
    """Same day N months later (the 31st becomes the last day of shorter months)."""
    year, month = divmod(date.month - 1 + months, 12)
    year, month = date.year + year, month + 1
    return date.replace(
        year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1])
    )


@transaction.atomic
def create_entry(*, installments, first_due_date, user, **fields):
    """Create an entry with `parcelas` monthly installments from `primeiro_vencimento`."""
    entry = Entry.objects.create(created_by=user, **fields)
    # One by one (at most 48), not bulk_create, so the audit log records each installment.
    for number, amount in enumerate(split(entry.total_amount, installments), start=1):
        Installment.objects.create(
            clinic=entry.clinic,
            entry=entry,
            number=number,
            due_date=add_months(first_due_date, number - 1),
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
        raise ValidationError(_("This entry was cancelled."))
    payment = Payment(clinic=installment.clinic, installment=installment, created_by=user, **fields)
    check_period(payment.clinic_id, payment.date)
    _paid, balance = installment.paid_and_balance()
    if payment.principal <= 0:
        raise ValidationError(
            _("The amount deducted from the installment must be greater than zero.")
        )
    if payment.principal > balance:
        raise ValidationError(
            _(
                "The amount deducted (%(deducted)s) exceeds what is left of the installment "
                "(%(balance)s)."
            )
            % {"deducted": payment.principal, "balance": balance}
        )
    payment.save()
    return payment


@transaction.atomic
def reverse_payment(payment, *, reason, user):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.reversed:
        raise ValidationError(_("This payment was already reversed."))
    check_period(payment.clinic_id, payment.date)
    payment.reversed = True
    payment.reversed_at = timezone.now()
    payment.reversed_by = user
    payment.reversal_reason = reason
    # Only these fields: the commission links are set elsewhere and must not be overwritten.
    payment.save(update_fields=["reversed", "reversed_at", "reversed_by", "reversal_reason"])
    # A reversed payment no longer explains its bank statement line (saved, not .update(),
    # so the audit log records it).
    for bank_transaction in BankTransaction.objects.filter(payment=payment):
        bank_transaction.payment = None
        bank_transaction.status = BankTransaction.Status.PENDING
        bank_transaction.reconciled_by = None
        bank_transaction.reconciled_at = None
        bank_transaction.save()
    return payment


@transaction.atomic
def cancel(entry, *, reason, user):
    """Cancel an entry. Payments must be reversed first (they are real money).

    The entry row is locked: receber() locks it too (through its installment), so a
    payment cannot be recorded while the entry is being cancelled.
    """
    entry = Entry.objects.select_for_update().get(pk=entry.pk)
    if entry.cancelled:
        raise ValidationError(_("This entry was already cancelled."))
    if Payment.objects.filter(installment__entry=entry, reversed=False).exists():
        raise ValidationError(_("This entry has payments. Reverse the payments before cancelling."))
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
                "Finance is closed up to %(until)s: payments and reversals on or before that date "
                "cannot be recorded. Use a later date or ask the administrator to reopen the "
                "period."
            )
            % {"until": date_format(until, "SHORT_DATE_FORMAT")}
        )


@transaction.atomic
def close_books(clinic, until, *, user):
    """Close the books up to `ate` (at most yesterday: today's cash is still moving)."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    if until >= timezone.localdate():
        raise ValidationError(
            _("Close up to yesterday at the latest: money is still moving today.")
        )
    current = closed_until(clinic.pk)
    if current is not None and until <= current:
        raise ValidationError(
            _("Finance is already closed up to %(until)s. To go back, reopen the period.")
            % {"until": date_format(current, "SHORT_DATE_FORMAT")}
        )
    return BookClosing.objects.create(clinic=clinic, until=until, created_by=user)


@transaction.atomic
def reopen_books(clinic, until, *, reason, user):
    """Move the closing back to `ate` (None opens everything). A reason is required."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    current = closed_until(clinic.pk)
    if current is None:
        raise ValidationError(_("Finance is not closed."))
    if until is not None and until >= current:
        raise ValidationError(_("To reopen, choose a date before the current closing."))
    if not reason.strip():
        raise ValidationError(_("Enter the reason for reopening."))
    return BookClosing.objects.create(
        clinic=clinic, until=until, reason=reason.strip(), created_by=user
    )


def status(installment, today=None):
    """Status of an installment annotated with com_saldo() (code, label)."""
    today = today or timezone.localdate()
    if installment.entry.cancelled:
        return "cancelled", pgettext("feminine", "Cancelled")
    if installment.balance <= 0:
        return "paid", pgettext("feminine", "Paid")
    if installment.due_date < today:
        return "overdue", pgettext("feminine", "Overdue")
    if installment.paid > 0:
        return "partial", _("Partly paid")
    return "open", pgettext("installment", "Open")


def debtors(today=None):
    """Who owes the clinic, from the open installments of receivables.

    One row per patient (or payer name): overdue total split by days late, amount not yet
    due and the oldest due date, ordered by the overdue total.
    """
    today = today or timezone.localdate()
    # Plain values, not model instances: a clinic with years of use has thousands of open
    # installments, and full objects took tens of MB per request (volume test, decision 108).
    installments = (
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
    for installment in installments:
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
        delay = (today - due_date).days
        band = next(
            (i for i, limit in enumerate(OVERDUE_BRACKETS) if delay <= limit),
            len(OVERDUE_BRACKETS),
        )
        row["brackets"][band] += balance
        row["overdue"] += balance
        if row["oldest"] is None or due_date < row["oldest"]:
            row["oldest"] = due_date
    result = [row for row in rows.values() if row["overdue"] or row["not_yet_due"]]
    return sorted(result, key=lambda row: (-row["overdue"], alphabetical_key(row["name"])))


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

    payments = valid_payments()
    if until is not None:
        payments = payments.filter(date__lte=until)
    cash_movement = defaultdict(lambda: ZERO)
    for account_id, kind, total in (
        payments.order_by()
        .values_list("account_id", "installment__entry__kind")
        .annotate(total=Sum("amount"))
    ):
        cash_movement[account_id] += _sign(kind) * total
    movements = CashMovement.objects.all()
    if until is not None:
        movements = movements.filter(created_at__date__lte=until)
    for account_id, other_id, kind, total in (
        movements.order_by()
        .values_list("cash_register__account_id", "other_account_id", "kind")
        .annotate(total=Sum("amount"))
    ):
        # A withdrawal leaves the drawer (into the other account, if any); a top-up enters it.
        sign = -1 if kind == CashMovement.Kind.WITHDRAWAL else 1
        cash_movement[account_id] += sign * total
        if other_id:
            cash_movement[other_id] -= sign * total
    return [
        (account, account.opening_balance + cash_movement[account.pk])
        for account in FinancialAccount.objects.all().order_by("name")
    ]


def cash_flow(since, until, by_month=False, today=None):
    """Rows per day (or month) from `de` to `ate`.

    Actual = payments made (by payment date); expected = what is still open in the
    installments due in the period (overdue ones included, flagged by the date). The
    running balance starts from the accounts' balance on the day before `de` and adds both.
    """
    today = today or timezone.localdate()

    def key(date):
        return date.replace(day=1) if by_month else date

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
    result = []
    for date in sorted(rows):
        row = rows[date]
        row["date"] = date
        row["late"] = (
            not by_month and date < today and (row["expected_incoming"] or row["expected_outgoing"])
        )
        balance += (
            row["incoming"] - row["outgoing"] + row["expected_incoming"] - row["expected_outgoing"]
        )
        row["balance"] = balance
        result.append(row)
    totals = {
        field: sum((row[field] for row in result), start=ZERO)
        for field in ("incoming", "outgoing", "expected_incoming", "expected_outgoing")
    }
    return {
        "rows": result,
        "totals": totals,
        "opening_balance": opening_balance,
        "closing_balance": balance,
    }


def received_and_paid(since, until):
    """(money received, money paid) from `de` to `ate`, in one query (home page, 0.24.0)."""
    totals = dict(
        valid_payments()
        .filter(date__gte=since, date__lte=until)
        .order_by()
        .values_list("installment__entry__kind")
        .annotate(total=Sum("amount"))
    )
    return totals.get(Entry.Kind.RECEIVABLE, ZERO), totals.get(Entry.Kind.PAYABLE, ZERO)


def report(since, until):
    """Money received and paid in the period, grouped for the reports page."""
    payments = valid_payments().filter(date__gte=since, date__lte=until)
    received_payments = payments.filter(installment__entry__kind=Entry.Kind.RECEIVABLE)
    paid_payments = payments.filter(installment__entry__kind=Entry.Kind.PAYABLE)

    def group_by(query, field, label=None):
        groups = query.order_by().values_list(field).annotate(total=Sum("amount"))
        rows = [((label or {}).get(key, key), total) for key, total in groups]
        return sorted(rows, key=lambda row: -row[1])

    def add_up(query, field):
        return query.aggregate(total=Coalesce(Sum(field), ZERO, output_field=MONEY))["total"]

    methods = method_labels()
    total_received = add_up(received_payments, "amount")
    total_paid = add_up(paid_payments, "amount")
    # The chart of accounts (decision 097) only once the clinic has groups.
    groups = AccountGroup.objects.exists()
    # Cost centers (decision 095) only once the clinic has registered one.
    cost_centers = CostCenter.objects.exists()
    no_cost_center = {None: _("No cost center")}
    cost_center = "installment__entry__cost_center__name"
    return {
        "groups": groups,
        "by_group": tree_by_group(received_payments, Category.Kind.INCOME) if groups else [],
        "expenses_by_group": tree_by_group(paid_payments, Category.Kind.EXPENSE) if groups else [],
        "centers": cost_centers,
        "by_center": group_by(received_payments, cost_center, no_cost_center)
        if cost_centers
        else [],
        "expenses_by_center": group_by(paid_payments, cost_center, no_cost_center)
        if cost_centers
        else [],
        "by_method": group_by(received_payments, "method", methods),
        "by_category": group_by(received_payments, "installment__entry__category__name"),
        "by_practitioner": group_by(received_payments, "installment__entry__practitioner__name"),
        "expenses_by_category": group_by(paid_payments, "installment__entry__category__name"),
        "total_received": total_received,
        "total_paid": total_paid,
        "result": total_received - total_paid,
        "discounts": add_up(received_payments, "discount"),
        "interest": add_up(received_payments, "interest"),
    }


def link_groups(query):
    """The groups with each parent set from the same list, so numbers like 2.1 are
    built without one query per level."""
    groups = list(query)
    by_id = {group.pk: group for group in groups}
    for group in groups:
        if group.parent_id in by_id:
            group.parent = by_id[group.parent_id]
    return groups


def in_tree_order(groups):
    """(level, group) pairs in chart order: each group followed by its subgroups."""
    children = defaultdict(list)
    for group in groups:  # already in chart order (code, then name)
        children[group.parent_id].append(group)
    output = []

    def walk_down(parent_id, level):
        for group in children[parent_id]:
            output.append((level, group))
            walk_down(group.pk, level + 1)

    walk_down(None, 0)
    return output


def totals_by_group(payments, kind):
    """Payments summed by group, each group including its subgroups.

    Returns (groups of the type, {group id: total}, total of categories outside any group).
    """
    by_category = dict(
        payments.order_by()
        .values_list("installment__entry__category_id")
        .annotate(total=Sum("amount"))
    )
    category_group = dict(Category.objects.filter(kind=kind).values_list("pk", "group_id"))
    groups = link_groups(AccountGroup.objects.filter(kind=kind))
    parent = {group.pk: group.parent_id for group in groups}
    totals = defaultdict(lambda: ZERO)
    ungrouped = ZERO
    for category_id, amount in by_category.items():
        group_id = category_group.get(category_id)
        if group_id is None:
            ungrouped += amount
        while group_id is not None:
            totals[group_id] += amount
            group_id = parent.get(group_id)
    return groups, totals, ungrouped


def tree_by_group(payments, kind):
    """(level, name, total) rows in tree order for the reports, groups without money left
    out, and a last row for the categories outside any group."""
    groups, totals, ungrouped = totals_by_group(payments, kind)
    rows = [
        (level, str(group), totals[group.pk])
        for level, group in in_tree_order(groups)
        if totals[group.pk]
    ]
    if ungrouped:
        rows.append((0, _("No group"), ungrouped))
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
    fraction = year_fraction(year, today)
    goals = dict(Planning.objects.filter(year=year).values_list("group_id", "amount"))
    payments = valid_payments().filter(date__year=year)
    sections = []
    for kind, label, entries in (
        (Category.Kind.INCOME, pgettext("plural", "Income"), Entry.Kind.RECEIVABLE),
        (Category.Kind.EXPENSE, _("Expenses"), Entry.Kind.PAYABLE),
    ):
        groups, totals, ungrouped = totals_by_group(
            payments.filter(installment__entry__kind=entries), kind
        )
        rows, meta_total, covered = [], ZERO, set()
        for level, group in in_tree_order(groups):
            meta, actual = goals.get(group.pk), totals[group.pk]
            if not group.active and meta is None and not actual:
                continue
            if meta and group.parent_id not in covered:
                meta_total += meta
            if meta or group.parent_id in covered:
                covered.add(group.pk)
            expected = (meta * fraction).quantize(CENT) if meta else None
            rows.append(
                {
                    "level": level,
                    "group": group,
                    "target": meta,
                    "actual": actual,
                    "expected": expected,
                    "percentage": round(100 * actual / meta) if meta else None,
                    # On track: income at or above where it should be, expenses at or below.
                    "on_track": None
                    if not meta
                    else actual >= expected
                    if kind == Category.Kind.INCOME
                    else actual <= expected,
                }
            )
        actual_total = sum((totals[g.pk] for g in groups if g.parent_id is None), ZERO) + ungrouped
        sections.append(
            {
                "kind": kind,
                "label": label,
                "rows": rows,
                "ungrouped": ungrouped,
                "target": meta_total,
                "expected": (meta_total * fraction).quantize(CENT),
                "actual": actual_total,
            }
        )
    return {"year": year, "fraction": fraction, "sections": sections}


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
    existing = set(Planning.objects.filter(year=year).values_list("group_id", flat=True))
    copied = 0
    for previous in Planning.objects.filter(year=year - 1).exclude(group_id__in=existing):
        # One by one, not bulk_create, so the audit log records each goal.
        Planning.objects.create(year=year, group_id=previous.group_id, amount=previous.amount)
        copied += 1
    return copied


# --- Daily cash drawer (0.17.0) ----------------------------------------------------------


def open_cash_register(account):
    return CashRegister.objects.filter(account=account, closed_at__isnull=True).first()


@transaction.atomic
def open_register(account, *, amount, user):
    if open_cash_register(account) is not None:
        raise ValidationError(_("This account's drawer is already open."))
    return CashRegister.objects.create(
        clinic=account.clinic, account=account, opening_amount=amount, opened_by=user
    )


def register_summary(cash_register):
    """Money that went through the drawer since it was opened, and the expected amount.

    Payments count by the moment they were registered (not their date), so a payment
    typed in today for last week still lands in today's drawer.
    """
    end = cash_register.closed_at or timezone.now()
    payments = list(
        valid_payments()
        .filter(
            account=cash_register.account,
            created_at__gte=cash_register.opened_at,
            created_at__lte=end,
        )
        .select_related("installment__entry__patient")
        .order_by("created_at")
    )
    movements = list(cash_register.movements.select_related("other_account", "created_by"))
    inflows = sum(
        (p.amount for p in payments if p.installment.entry.kind == Entry.Kind.RECEIVABLE),
        start=ZERO,
    )
    outflows = sum(
        (p.amount for p in payments if p.installment.entry.kind == Entry.Kind.PAYABLE),
        start=ZERO,
    )
    top_ups = sum((m.amount for m in movements if m.kind == CashMovement.Kind.TOP_UP), start=ZERO)
    withdrawals = sum(
        (m.amount for m in movements if m.kind == CashMovement.Kind.WITHDRAWAL), start=ZERO
    )
    return {
        "payments": payments,
        "movements": movements,
        "incoming": inflows,
        "outgoing": outflows,
        "top_ups": top_ups,
        "withdrawals": withdrawals,
        "expected": cash_register.opening_amount + inflows - outflows + top_ups - withdrawals,
    }


@transaction.atomic
def move_cash(cash_register, *, kind, amount, reason, user, other_account=None):
    cash_register = CashRegister.objects.select_for_update().get(pk=cash_register.pk)
    if not cash_register.is_open:
        raise ValidationError(_("This drawer is already closed."))
    if other_account is not None and other_account.pk == cash_register.account_id:
        raise ValidationError(_("Choose an account other than the drawer's."))
    if (
        kind == CashMovement.Kind.WITHDRAWAL
        and amount > register_summary(cash_register)["expected"]
    ):
        raise ValidationError(_("The withdrawal exceeds what should be in the drawer."))
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
        raise ValidationError(_("This drawer is already closed."))
    cash_register.expected_amount = register_summary(cash_register)["expected"]
    cash_register.counted_amount = counted_amount
    cash_register.note = note
    cash_register.closed_at = timezone.now()
    cash_register.closed_by = user
    cash_register.save()
    return cash_register
