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

JANELA = datetime.timedelta(days=10)
Situacao = BankTransaction.Situacao


@transaction.atomic
def importar(account, *, nome_arquivo, content, user):
    """Read an OFX file into `conta`. Lines imported before (same bank id) are skipped."""
    extrato = ofx.ler(content)
    if not extrato.transacoes:
        raise ofx.ArquivoInvalido(_("O extrato não tem transações."))
    statement_import = StatementImport.objects.create(
        clinic=account.clinic,
        account=account,
        file=nome_arquivo[:200],
        bank_code=extrato.bank_code,
        bank_account_number=extrato.account,
        start=extrato.start or min(t.date for t in extrato.transacoes),
        end=extrato.end or max(t.date for t in extrato.transacoes),
        balance=extrato.balance,
        balance_date=extrato.balance_date or extrato.end,
        unreadable_transactions=extrato.unreadable_transactions,
        created_by=user,
    )
    existentes = set(
        BankTransaction.objects.filter(
            account=account, fitid__in=[t.fitid for t in extrato.transacoes]
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
            for t in extrato.transacoes
            if t.fitid not in existentes
        ],
        ignore_conflicts=True,  # another import of the same file at the same moment
    )
    # Counted in the database: with ignore_conflicts, bulk_create returns skipped rows too.
    statement_import.new_transactions = BankTransaction.objects.filter(
        statement_import=statement_import
    ).count()
    statement_import.duplicate_transactions = (
        len(extrato.transacoes) - statement_import.new_transactions
    )
    statement_import.save(update_fields=["new_transactions", "duplicate_transactions"])
    return statement_import


def outra_conta_no_banco(statement_import):
    """The bank account number of an earlier import into the same account, if different."""
    anterior = (
        StatementImport.objects.filter(account=statement_import.account)
        .exclude(pk=statement_import.pk)
        .exclude(bank_account_number="")
        .first()
    )
    if (
        anterior
        and statement_import.bank_account_number
        and anterior.bank_account_number != statement_import.bank_account_number
    ):
        return anterior.bank_account_number
    return None


@dataclass
class Candidato:
    chave: str  # "p<pk>" for a payment, "m<pk>" for a drawer movement
    date: datetime.date
    description: str
    objeto: object


def candidatos(transacoes):
    """{transaction pk: [Candidato, closest date first]} for the pending transactions."""
    pendentes = [t for t in transacoes if t.status == Situacao.PENDENTE]
    if not pendentes:
        return {}
    contas = {t.account_id for t in pendentes}
    de = min(t.date for t in pendentes) - JANELA
    until = max(t.date for t in pendentes) + JANELA
    pagamentos = list(
        Payment.objects.filter(
            account_id__in=contas, reversed=False, transacao__isnull=True, date__range=(de, until)
        ).select_related("installment__entry__patient")
    )
    movimentos = list(
        CashMovement.objects.filter(
            other_account_id__in=contas,
            transacao__isnull=True,
            created_at__date__range=(de, until),
        ).select_related("cash_register__account")
    )
    resultado = {}
    for t in pendentes:
        amount = abs(t.amount)
        kind = Entry.Tipo.RECEBER if t.entrada else Entry.Tipo.PAGAR
        # Money taken out of the drawer into the bank is a credit there, and vice versa.
        tipo_movimento = CashMovement.Tipo.RETIRADA if t.entrada else CashMovement.Tipo.REFORCO
        lista = []
        for p in pagamentos:
            entry = p.installment.entry
            if (
                p.account_id == t.account_id
                and p.amount == amount
                and entry.kind == kind
                and abs(p.date - t.date) <= JANELA
            ):
                lista.append(
                    Candidato(
                        f"p{p.pk}",
                        p.date,
                        f"{entry.nome_pessoa} · {entry.description}",
                        p,
                    )
                )
        for m in movimentos:
            date = timezone.localtime(m.created_at).date()
            if (
                m.other_account_id == t.account_id
                and m.amount == amount
                and m.kind == tipo_movimento
                and abs(date - t.date) <= JANELA
            ):
                lista.append(
                    Candidato(
                        f"m{m.pk}",
                        date,
                        f"{m.cash_register.account} · {m.get_kind_display()}: {m.reason}",
                        m,
                    )
                )
        lista.sort(key=lambda c: (abs(c.date - t.date), c.date, c.chave))
        resultado[t.pk] = lista
    return resultado


def _vincular(transacao, candidato, user):
    if isinstance(candidato.objeto, Payment):
        transacao.payment = candidato.objeto
    else:
        transacao.cash_movement = candidato.objeto
    transacao.status = Situacao.CONCILIADA
    transacao.reconciled_by = user
    transacao.reconciled_at = timezone.now()
    try:
        with transaction.atomic():
            transacao.save()
    except IntegrityError:
        # Someone reconciled the same payment with another line a moment ago.
        raise ValidationError(_("Esse lançamento já foi conciliado com outra transação.")) from None


def _pendente(transacao):
    transacao = BankTransaction.objects.select_for_update().get(pk=transacao.pk)
    if transacao.status != Situacao.PENDENTE:
        raise ValidationError(_("Esta transação já foi conciliada ou ignorada."))
    return transacao


@transaction.atomic
def conciliar(transacao, chave, *, user):
    transacao = _pendente(transacao)
    for candidato in candidatos([transacao]).get(transacao.pk, []):
        if candidato.chave == chave:
            _vincular(transacao, candidato, user)
            return transacao
    raise ValidationError(_("Esse lançamento não corresponde a esta transação."))


@transaction.atomic
def conciliar_unicos(statement_import, *, user):
    """Reconcile every pending line with exactly one candidate that no other line wants."""
    transacoes = list(
        BankTransaction.objects.select_for_update().filter(
            statement_import=statement_import, status=Situacao.PENDENTE
        )
    )
    por_transacao = candidatos(transacoes)
    procurados = Counter(c.chave for lista in por_transacao.values() for c in lista)
    feitas = 0
    for t in transacoes:
        lista = por_transacao.get(t.pk, [])
        if len(lista) == 1 and procurados[lista[0].chave] == 1:
            _vincular(t, lista[0], user)
            feitas += 1
    return feitas


@transaction.atomic
def criar_lancamento(transacao, *, description, category, payer, method, user):
    """A new entry, already paid on the statement date, for a line the system did not know."""
    transacao = _pendente(transacao)
    entry = services.criar_lancamento(
        clinic=transacao.clinic,
        kind=Entry.Tipo.RECEBER if transacao.entrada else Entry.Tipo.PAGAR,
        payer=payer or description,
        description=description,
        category=category,
        total_amount=abs(transacao.amount),
        parcelas=1,
        primeiro_vencimento=transacao.date,
        user=user,
    )
    payment = services.receber(
        entry.parcelas.get(),
        user=user,
        amount=abs(transacao.amount),
        method=method,
        account=transacao.account,
        date=transacao.date,
    )
    _vincular(transacao, Candidato(f"p{payment.pk}", payment.date, "", payment), user)
    return entry


@transaction.atomic
def ignorar(transacao, *, reason, user):
    transacao = _pendente(transacao)
    transacao.status = Situacao.IGNORADA
    transacao.reason = reason
    transacao.reconciled_by = user
    transacao.reconciled_at = timezone.now()
    transacao.save()


@transaction.atomic
def desfazer(transacao):
    """Back to pending. An entry created from the line stays (cancel it if it was wrong)."""
    transacao = BankTransaction.objects.select_for_update().get(pk=transacao.pk)
    transacao.status = Situacao.PENDENTE
    transacao.payment = None
    transacao.cash_movement = None
    transacao.reason = ""
    transacao.reconciled_by = None
    transacao.reconciled_at = None
    transacao.save()


def saldo_no_sistema(statement_import):
    """The system's balance of the account on the bank balance date (None without one)."""
    if statement_import.balance is None or statement_import.balance_date is None:
        return None
    for account, balance in services.saldos_das_contas(until=statement_import.balance_date):
        if account.pk == statement_import.account_id:
            return balance
    return None
