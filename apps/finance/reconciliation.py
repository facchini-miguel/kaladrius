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
def import_statement(account, *, nome_arquivo, content, user):
    """Read an OFX file into `conta`. Lines imported before (same bank id) are skipped."""
    statement = ofx.read(content)
    if not statement.transacoes:
        raise ofx.InvalidFile(_("O extrato não tem transações."))
    statement_import = StatementImport.objects.create(
        clinic=account.clinic,
        account=account,
        file=nome_arquivo[:200],
        bank_code=statement.bank_code,
        bank_account_number=statement.account,
        start=statement.start or min(t.date for t in statement.transacoes),
        end=statement.end or max(t.date for t in statement.transacoes),
        balance=statement.balance,
        balance_date=statement.balance_date or statement.end,
        unreadable_transactions=statement.unreadable_transactions,
        created_by=user,
    )
    existentes = set(
        BankTransaction.objects.filter(
            account=account, fitid__in=[t.fitid for t in statement.transacoes]
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
            for t in statement.transacoes
            if t.fitid not in existentes
        ],
        ignore_conflicts=True,  # another import of the same file at the same moment
    )
    # Counted in the database: with ignore_conflicts, bulk_create returns skipped rows too.
    statement_import.new_transactions = BankTransaction.objects.filter(
        statement_import=statement_import
    ).count()
    statement_import.duplicate_transactions = (
        len(statement.transacoes) - statement_import.new_transactions
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


def candidates(transacoes):
    """{transaction pk: [Candidato, closest date first]} for the pending transactions."""
    pendentes = [t for t in transacoes if t.status == Status.PENDING]
    if not pendentes:
        return {}
    contas = {t.account_id for t in pendentes}
    since = min(t.date for t in pendentes) - WINDOW
    until = max(t.date for t in pendentes) + WINDOW
    pagamentos = list(
        Payment.objects.filter(
            account_id__in=contas,
            reversed=False,
            transaction__isnull=True,
            date__range=(since, until),
        ).select_related("installment__entry__patient")
    )
    movimentos = list(
        CashMovement.objects.filter(
            other_account_id__in=contas,
            transaction__isnull=True,
            created_at__date__range=(since, until),
        ).select_related("cash_register__account")
    )
    resultado = {}
    for t in pendentes:
        amount = abs(t.amount)
        kind = Entry.Kind.RECEIVABLE if t.is_incoming else Entry.Kind.PAYABLE
        # Money taken out of the drawer into the bank is a credit there, and vice versa.
        tipo_movimento = CashMovement.Kind.WITHDRAWAL if t.is_incoming else CashMovement.Kind.TOP_UP
        results = []
        for p in pagamentos:
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
        for m in movimentos:
            date = timezone.localtime(m.created_at).date()
            if (
                m.other_account_id == t.account_id
                and m.amount == amount
                and m.kind == tipo_movimento
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
        resultado[t.pk] = results
    return resultado


def _link(transacao, candidato, user):
    if isinstance(candidato.obj, Payment):
        transacao.payment = candidato.obj
    else:
        transacao.cash_movement = candidato.obj
    transacao.status = Status.RECONCILED
    transacao.reconciled_by = user
    transacao.reconciled_at = timezone.now()
    try:
        with transaction.atomic():
            transacao.save()
    except IntegrityError:
        # Someone reconciled the same payment with another line a moment ago.
        raise ValidationError(_("Esse lançamento já foi conciliado com outra transação.")) from None


def _pending(transacao):
    transacao = BankTransaction.objects.select_for_update().get(pk=transacao.pk)
    if transacao.status != Status.PENDING:
        raise ValidationError(_("Esta transação já foi conciliada ou ignorada."))
    return transacao


@transaction.atomic
def reconcile(transacao, key, *, user):
    transacao = _pending(transacao)
    for candidato in candidates([transacao]).get(transacao.pk, []):
        if candidato.key == key:
            _link(transacao, candidato, user)
            return transacao
    raise ValidationError(_("Esse lançamento não corresponde a esta transação."))


@transaction.atomic
def reconcile_unique(statement_import, *, user):
    """Reconcile every pending line with exactly one candidate that no other line wants."""
    transacoes = list(
        BankTransaction.objects.select_for_update().filter(
            statement_import=statement_import, status=Status.PENDING
        )
    )
    por_transacao = candidates(transacoes)
    procurados = Counter(c.key for results in por_transacao.values() for c in results)
    feitas = 0
    for t in transacoes:
        results = por_transacao.get(t.pk, [])
        if len(results) == 1 and procurados[results[0].key] == 1:
            _link(t, results[0], user)
            feitas += 1
    return feitas


@transaction.atomic
def create_entry(transacao, *, description, category, payer, method, user):
    """A new entry, already paid on the statement date, for a line the system did not know."""
    transacao = _pending(transacao)
    entry = services.create_entry(
        clinic=transacao.clinic,
        kind=Entry.Kind.RECEIVABLE if transacao.is_incoming else Entry.Kind.PAYABLE,
        payer=payer or description,
        description=description,
        category=category,
        total_amount=abs(transacao.amount),
        parcelas=1,
        primeiro_vencimento=transacao.date,
        user=user,
    )
    payment = services.receive(
        entry.installments.get(),
        user=user,
        amount=abs(transacao.amount),
        method=method,
        account=transacao.account,
        date=transacao.date,
    )
    _link(transacao, Candidate(f"p{payment.pk}", payment.date, "", payment), user)
    return entry


@transaction.atomic
def ignore(transacao, *, reason, user):
    transacao = _pending(transacao)
    transacao.status = Status.IGNORED
    transacao.reason = reason
    transacao.reconciled_by = user
    transacao.reconciled_at = timezone.now()
    transacao.save()


@transaction.atomic
def undo(transacao):
    """Back to pending. An entry created from the line stays (cancel it if it was wrong)."""
    transacao = BankTransaction.objects.select_for_update().get(pk=transacao.pk)
    transacao.status = Status.PENDING
    transacao.payment = None
    transacao.cash_movement = None
    transacao.reason = ""
    transacao.reconciled_by = None
    transacao.reconciled_at = None
    transacao.save()


def system_balance(statement_import):
    """The system's balance of the account on the bank balance date (None without one)."""
    if statement_import.balance is None or statement_import.balance_date is None:
        return None
    for account, balance in services.account_balances(until=statement_import.balance_date):
        if account.pk == statement_import.account_id:
            return balance
    return None
