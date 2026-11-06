"""Bank statement import and reconciliation (0.20.0, decision 054).

Each statement line (TransacaoBancaria) is reconciled with what the system already knows
about that account: a payment received or made (same account, same amount, date within
JANELA) or a cash drawer movement to or from it. Lines with nothing to match (bank fees,
a transfer nobody recorded) become a new entry, already paid, or are ignored with a reason.
"""

import datetime
from collections import Counter
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from . import ofx, services
from .models import (
    BankTransaction,
    CashMovement,
    Entry,
    Payment,
    StatementImport,
)

WINDOW = datetime.timedelta(days=10)
Status = BankTransaction.Status


@transaction.atomic
def import_statement(account, *, file_name, content, user):
    """Read an OFX file into `conta`. Lines imported before (same bank id) are skipped."""
    statement = ofx.read(content)
    if not statement.transactions:
        raise ofx.InvalidFile(_("O extrato não tem transações."))
    statement_import = StatementImport.objects.create(
        clinic=account.clinic,
        account=account,
        file=file_name[:200],
        bank_code=statement.bank_code,
        bank_account_number=statement.account,
        start=statement.start or min(t.date for t in statement.transactions),
        end=statement.end or max(t.date for t in statement.transactions),
        balance=statement.balance,
        balance_date=statement.balance_date or statement.end,
        unreadable_transactions=statement.unreadable_transactions,
        created_by=user,
    )
    existing = set(
        BankTransaction.objects.filter(
            account=account, fitid__in=[t.fitid for t in statement.transactions]
        ).values_list("fitid", flat=True)
    )
    # In bulk (a statement can have hundreds of lines): the audit log records the import.
    BankTransaction.objects.bulk_create(
        [
            BankTransaction(
                clinic=account.clinic,
                account=account,
                statement_import=statement_import,
                fitid=t.fitid,
                date=t.date,
                amount=t.amount,
                description=t.description,
                kind=t.kind,
            )
            for t in statement.transactions
            if t.fitid not in existing
        ],
        ignore_conflicts=True,  # another import of the same file at the same moment
    )
    # Counted in the database: with ignore_conflicts, bulk_create returns skipped rows too.
    statement_import.new_transactions = BankTransaction.objects.filter(
        statement_import=statement_import
    ).count()
    statement_import.duplicate_transactions = (
        len(statement.transactions) - statement_import.new_transactions
    )
    statement_import.save(update_fields=["new_transactions", "duplicate_transactions"])
    return statement_import


def other_bank_account(statement_import):
    """The bank account number of an earlier import into the same account, if different."""
    previous = (
        StatementImport.objects.filter(account=statement_import.account)
        .exclude(pk=statement_import.pk)
        .exclude(bank_account_number="")
        .first()
    )
    if (
        previous
        and statement_import.bank_account_number
        and previous.bank_account_number != statement_import.bank_account_number
    ):
        return previous.bank_account_number
    return None


@dataclass
class Candidate:
    key: str  # "p<pk>" for a payment, "m<pk>" for a drawer movement
    date: datetime.date
    description: str
    obj: object


def candidates(transactions):
    """{transaction pk: [Candidato, closest date first]} for the pending transactions."""
    pending = [t for t in transactions if t.status == Status.PENDING]
    if not pending:
        return {}
    accounts = {t.account_id for t in pending}
    since = min(t.date for t in pending) - WINDOW
    until = max(t.date for t in pending) + WINDOW
    payments = list(
        Payment.objects.filter(
            account_id__in=accounts,
            reversed=False,
            transaction__isnull=True,
            date__range=(since, until),
        ).select_related("installment__entry__patient")
    )
    movements = list(
        CashMovement.objects.filter(
            other_account_id__in=accounts,
            transaction__isnull=True,
            created_at__date__range=(since, until),
        ).select_related("cash_register__account")
    )
    result = {}
    for t in pending:
        amount = abs(t.amount)
        kind = Entry.Kind.RECEIVABLE if t.is_incoming else Entry.Kind.PAYABLE
        # Money taken out of the drawer into the bank is a credit there, and vice versa.
        movement_kind = CashMovement.Kind.WITHDRAWAL if t.is_incoming else CashMovement.Kind.TOP_UP
        results = []
        for p in payments:
            entry = p.installment.entry
            if (
                p.account_id == t.account_id
                and p.amount == amount
                and entry.kind == kind
                and abs(p.date - t.date) <= WINDOW
            ):
                results.append(
                    Candidate(
                        f"p{p.pk}",
                        p.date,
                        f"{entry.payer_name} · {entry.description}",
                        p,
                    )
                )
        for m in movements:
            date = timezone.localtime(m.created_at).date()
            if (
                m.other_account_id == t.account_id
                and m.amount == amount
                and m.kind == movement_kind
                and abs(date - t.date) <= WINDOW
            ):
                results.append(
                    Candidate(
                        f"m{m.pk}",
                        date,
                        f"{m.cash_register.account} · {m.get_kind_display()}: {m.reason}",
                        m,
                    )
                )
        results.sort(key=lambda c: (abs(c.date - t.date), c.date, c.key))
        result[t.pk] = results
    return result


def _link(bank_transaction, candidate, user):
    if isinstance(candidate.obj, Payment):
        bank_transaction.payment = candidate.obj
    else:
        bank_transaction.cash_movement = candidate.obj
    bank_transaction.status = Status.RECONCILED
    bank_transaction.reconciled_by = user
    bank_transaction.reconciled_at = timezone.now()
    try:
        with transaction.atomic():
            bank_transaction.save()
    except IntegrityError:
        # Someone reconciled the same payment with another line a moment ago.
        raise ValidationError(_("Esse lançamento já foi conciliado com outra transação.")) from None


def _pending(bank_transaction):
    bank_transaction = BankTransaction.objects.select_for_update().get(pk=bank_transaction.pk)
    if bank_transaction.status != Status.PENDING:
        raise ValidationError(_("Esta transação já foi conciliada ou ignorada."))
    return bank_transaction


@transaction.atomic
def reconcile(bank_transaction, key, *, user):
    bank_transaction = _pending(bank_transaction)
    for candidate in candidates([bank_transaction]).get(bank_transaction.pk, []):
        if candidate.key == key:
            _link(bank_transaction, candidate, user)
            return bank_transaction
    raise ValidationError(_("Esse lançamento não corresponde a esta transação."))


@transaction.atomic
def reconcile_unique(statement_import, *, user):
    """Reconcile every pending line with exactly one candidate that no other line wants."""
    transactions = list(
        BankTransaction.objects.select_for_update().filter(
            statement_import=statement_import, status=Status.PENDING
        )
    )
    by_transaction = candidates(transactions)
    wanted = Counter(c.key for results in by_transaction.values() for c in results)
    done = 0
    for t in transactions:
        results = by_transaction.get(t.pk, [])
        if len(results) == 1 and wanted[results[0].key] == 1:
            _link(t, results[0], user)
            done += 1
    return done


@transaction.atomic
def create_entry(bank_transaction, *, description, category, payer, method, user):
    """A new entry, already paid on the statement date, for a line the system did not know."""
    bank_transaction = _pending(bank_transaction)
    entry = services.create_entry(
        clinic=bank_transaction.clinic,
        kind=Entry.Kind.RECEIVABLE if bank_transaction.is_incoming else Entry.Kind.PAYABLE,
        payer=payer or description,
        description=description,
        category=category,
        total_amount=abs(bank_transaction.amount),
        installments=1,
        first_due_date=bank_transaction.date,
        user=user,
    )
    payment = services.receive(
        entry.installments.get(),
        user=user,
        amount=abs(bank_transaction.amount),
        method=method,
        account=bank_transaction.account,
        date=bank_transaction.date,
    )
    _link(bank_transaction, Candidate(f"p{payment.pk}", payment.date, "", payment), user)
    return entry


@transaction.atomic
def ignore(bank_transaction, *, reason, user):
    bank_transaction = _pending(bank_transaction)
    bank_transaction.status = Status.IGNORED
    bank_transaction.reason = reason
    bank_transaction.reconciled_by = user
    bank_transaction.reconciled_at = timezone.now()
    bank_transaction.save()


@transaction.atomic
def undo(bank_transaction):
    """Back to pending. An entry created from the line stays (cancel it if it was wrong)."""
    bank_transaction = BankTransaction.objects.select_for_update().get(pk=bank_transaction.pk)
    bank_transaction.status = Status.PENDING
    bank_transaction.payment = None
    bank_transaction.cash_movement = None
    bank_transaction.reason = ""
    bank_transaction.reconciled_by = None
    bank_transaction.reconciled_at = None
    bank_transaction.save()


def system_balance(statement_import):
    """The system's balance of the account on the bank balance date (None without one)."""
    if statement_import.balance is None or statement_import.balance_date is None:
        return None
    for account, balance in services.account_balances(until=statement_import.balance_date):
        if account.pk == statement_import.account_id:
            return balance
    return None
