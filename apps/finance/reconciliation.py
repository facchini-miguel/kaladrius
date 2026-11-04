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
def importar(account, *, nome_arquivo, conteudo, user):
    """Read an OFX file into `conta`. Lines imported before (same bank id) are skipped."""
    extrato = ofx.ler(conteudo)
    if not extrato.transacoes:
        raise ofx.ArquivoInvalido(_("O extrato não tem transações."))
    importacao = StatementImport.objects.create(
        clinic=account.clinic,
        account=account,
        file=nome_arquivo[:200],
        banco=extrato.banco,
        conta_no_banco=extrato.account,
        start=extrato.start or min(t.date for t in extrato.transacoes),
        end=extrato.end or max(t.date for t in extrato.transacoes),
        saldo=extrato.saldo,
        saldo_em=extrato.saldo_em or extrato.end,
        ignoradas=extrato.ignoradas,
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
                importacao=importacao,
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
    importacao.novas = BankTransaction.objects.filter(importacao=importacao).count()
    importacao.repetidas = len(extrato.transacoes) - importacao.novas
    importacao.save(update_fields=["novas", "repetidas"])
    return importacao


def outra_conta_no_banco(importacao):
    """The bank account number of an earlier import into the same account, if different."""
    anterior = (
        StatementImport.objects.filter(account=importacao.account)
        .exclude(pk=importacao.pk)
        .exclude(conta_no_banco="")
        .first()
    )
    if (
        anterior
        and importacao.conta_no_banco
        and anterior.conta_no_banco != importacao.conta_no_banco
    ):
        return anterior.conta_no_banco
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
            account_id__in=contas, estornado=False, transacao__isnull=True, date__range=(de, until)
        ).select_related("parcela__entry__patient")
    )
    movimentos = list(
        CashMovement.objects.filter(
            outra_conta_id__in=contas,
            transacao__isnull=True,
            created_at__date__range=(de, until),
        ).select_related("caixa__account")
    )
    resultado = {}
    for t in pendentes:
        amount = abs(t.amount)
        kind = Entry.Tipo.RECEBER if t.entrada else Entry.Tipo.PAGAR
        # Money taken out of the drawer into the bank is a credit there, and vice versa.
        tipo_movimento = CashMovement.Tipo.RETIRADA if t.entrada else CashMovement.Tipo.REFORCO
        lista = []
        for p in pagamentos:
            entry = p.parcela.entry
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
                m.outra_conta_id == t.account_id
                and m.amount == amount
                and m.kind == tipo_movimento
                and abs(date - t.date) <= JANELA
            ):
                lista.append(
                    Candidato(
                        f"m{m.pk}",
                        date,
                        f"{m.caixa.account} · {m.get_kind_display()}: {m.reason}",
                        m,
                    )
                )
        lista.sort(key=lambda c: (abs(c.date - t.date), c.date, c.chave))
        resultado[t.pk] = lista
    return resultado


def _vincular(transacao, candidato, user):
    if isinstance(candidato.objeto, Payment):
        transacao.pagamento = candidato.objeto
    else:
        transacao.movimento = candidato.objeto
    transacao.status = Situacao.CONCILIADA
    transacao.conciliado_por = user
    transacao.conciliado_em = timezone.now()
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
def conciliar_unicos(importacao, *, user):
    """Reconcile every pending line with exactly one candidate that no other line wants."""
    transacoes = list(
        BankTransaction.objects.select_for_update().filter(
            importacao=importacao, status=Situacao.PENDENTE
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
def criar_lancamento(transacao, *, description, category, pessoa, forma, user):
    """A new entry, already paid on the statement date, for a line the system did not know."""
    transacao = _pendente(transacao)
    entry = services.criar_lancamento(
        clinic=transacao.clinic,
        kind=Entry.Tipo.RECEBER if transacao.entrada else Entry.Tipo.PAGAR,
        pessoa=pessoa or description,
        description=description,
        category=category,
        valor_total=abs(transacao.amount),
        parcelas=1,
        primeiro_vencimento=transacao.date,
        user=user,
    )
    pagamento = services.receber(
        entry.parcelas.get(),
        user=user,
        amount=abs(transacao.amount),
        forma=forma,
        account=transacao.account,
        date=transacao.date,
    )
    _vincular(transacao, Candidato(f"p{pagamento.pk}", pagamento.date, "", pagamento), user)
    return entry


@transaction.atomic
def ignorar(transacao, *, reason, user):
    transacao = _pendente(transacao)
    transacao.status = Situacao.IGNORADA
    transacao.reason = reason
    transacao.conciliado_por = user
    transacao.conciliado_em = timezone.now()
    transacao.save()


@transaction.atomic
def desfazer(transacao):
    """Back to pending. An entry created from the line stays (cancel it if it was wrong)."""
    transacao = BankTransaction.objects.select_for_update().get(pk=transacao.pk)
    transacao.status = Situacao.PENDENTE
    transacao.pagamento = None
    transacao.movimento = None
    transacao.reason = ""
    transacao.conciliado_por = None
    transacao.conciliado_em = None
    transacao.save()


def saldo_no_sistema(importacao):
    """The system's balance of the account on the bank balance date (None without one)."""
    if importacao.saldo is None or importacao.saldo_em is None:
        return None
    for account, saldo in services.saldos_das_contas(until=importacao.saldo_em):
        if account.pk == importacao.account_id:
            return saldo
    return None
