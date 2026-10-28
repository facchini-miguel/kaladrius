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

from . import ofx, servicos
from .models import (
    ImportacaoExtrato,
    Lancamento,
    MovimentoCaixa,
    Pagamento,
    TransacaoBancaria,
)

JANELA = datetime.timedelta(days=10)
Situacao = TransacaoBancaria.Situacao


@transaction.atomic
def importar(conta, *, nome_arquivo, conteudo, usuario):
    """Read an OFX file into `conta`. Lines imported before (same bank id) are skipped."""
    extrato = ofx.ler(conteudo)
    if not extrato.transacoes:
        raise ofx.ArquivoInvalido(_("O extrato não tem transações."))
    importacao = ImportacaoExtrato.objects.create(
        clinica=conta.clinica,
        conta=conta,
        arquivo=nome_arquivo[:200],
        banco=extrato.banco,
        conta_no_banco=extrato.conta,
        inicio=extrato.inicio or min(t.data for t in extrato.transacoes),
        fim=extrato.fim or max(t.data for t in extrato.transacoes),
        saldo=extrato.saldo,
        saldo_em=extrato.saldo_em or extrato.fim,
        ignoradas=extrato.ignoradas,
        criado_por=usuario,
    )
    existentes = set(
        TransacaoBancaria.objects.filter(
            conta=conta, fitid__in=[t.fitid for t in extrato.transacoes]
        ).values_list("fitid", flat=True)
    )
    # In bulk (a statement can have hundreds of lines): the audit log records the import.
    TransacaoBancaria.objects.bulk_create(
        [
            TransacaoBancaria(
                clinica=conta.clinica,
                conta=conta,
                importacao=importacao,
                fitid=t.fitid,
                data=t.data,
                valor=t.valor,
                descricao=t.descricao,
                tipo=t.tipo,
            )
            for t in extrato.transacoes
            if t.fitid not in existentes
        ],
        ignore_conflicts=True,  # another import of the same file at the same moment
    )
    # Counted in the database: with ignore_conflicts, bulk_create returns skipped rows too.
    importacao.novas = TransacaoBancaria.objects.filter(importacao=importacao).count()
    importacao.repetidas = len(extrato.transacoes) - importacao.novas
    importacao.save(update_fields=["novas", "repetidas"])
    return importacao


def outra_conta_no_banco(importacao):
    """The bank account number of an earlier import into the same account, if different."""
    anterior = (
        ImportacaoExtrato.objects.filter(conta=importacao.conta)
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
    data: datetime.date
    descricao: str
    objeto: object


def candidatos(transacoes):
    """{transaction pk: [Candidato, closest date first]} for the pending transactions."""
    pendentes = [t for t in transacoes if t.situacao == Situacao.PENDENTE]
    if not pendentes:
        return {}
    contas = {t.conta_id for t in pendentes}
    de = min(t.data for t in pendentes) - JANELA
    ate = max(t.data for t in pendentes) + JANELA
    pagamentos = list(
        Pagamento.objects.filter(
            conta_id__in=contas, estornado=False, transacao__isnull=True, data__range=(de, ate)
        ).select_related("parcela__lancamento__paciente")
    )
    movimentos = list(
        MovimentoCaixa.objects.filter(
            outra_conta_id__in=contas,
            transacao__isnull=True,
            criado_em__date__range=(de, ate),
        ).select_related("caixa__conta")
    )
    resultado = {}
    for t in pendentes:
        valor = abs(t.valor)
        tipo = Lancamento.Tipo.RECEBER if t.entrada else Lancamento.Tipo.PAGAR
        # Money taken out of the drawer into the bank is a credit there, and vice versa.
        tipo_movimento = MovimentoCaixa.Tipo.RETIRADA if t.entrada else MovimentoCaixa.Tipo.REFORCO
        lista = []
        for p in pagamentos:
            lancamento = p.parcela.lancamento
            if (
                p.conta_id == t.conta_id
                and p.valor == valor
                and lancamento.tipo == tipo
                and abs(p.data - t.data) <= JANELA
            ):
                lista.append(
                    Candidato(
                        f"p{p.pk}", p.data, f"{lancamento.nome_pessoa} · {lancamento.descricao}", p
                    )
                )
        for m in movimentos:
            data = timezone.localtime(m.criado_em).date()
            if (
                m.outra_conta_id == t.conta_id
                and m.valor == valor
                and m.tipo == tipo_movimento
                and abs(data - t.data) <= JANELA
            ):
                lista.append(
                    Candidato(
                        f"m{m.pk}", data, f"{m.caixa.conta} · {m.get_tipo_display()}: {m.motivo}", m
                    )
                )
        lista.sort(key=lambda c: (abs(c.data - t.data), c.data, c.chave))
        resultado[t.pk] = lista
    return resultado


def _vincular(transacao, candidato, usuario):
    if isinstance(candidato.objeto, Pagamento):
        transacao.pagamento = candidato.objeto
    else:
        transacao.movimento = candidato.objeto
    transacao.situacao = Situacao.CONCILIADA
    transacao.conciliado_por = usuario
    transacao.conciliado_em = timezone.now()
    try:
        with transaction.atomic():
            transacao.save()
    except IntegrityError:
        # Someone reconciled the same payment with another line a moment ago.
        raise ValidationError(_("Esse lançamento já foi conciliado com outra transação.")) from None


def _pendente(transacao):
    transacao = TransacaoBancaria.objects.select_for_update().get(pk=transacao.pk)
    if transacao.situacao != Situacao.PENDENTE:
        raise ValidationError(_("Esta transação já foi conciliada ou ignorada."))
    return transacao


@transaction.atomic
def conciliar(transacao, chave, *, usuario):
    transacao = _pendente(transacao)
    for candidato in candidatos([transacao]).get(transacao.pk, []):
        if candidato.chave == chave:
            _vincular(transacao, candidato, usuario)
            return transacao
    raise ValidationError(_("Esse lançamento não corresponde a esta transação."))


@transaction.atomic
def conciliar_unicos(importacao, *, usuario):
    """Reconcile every pending line with exactly one candidate that no other line wants."""
    transacoes = list(
        TransacaoBancaria.objects.select_for_update().filter(
            importacao=importacao, situacao=Situacao.PENDENTE
        )
    )
    por_transacao = candidatos(transacoes)
    procurados = Counter(c.chave for lista in por_transacao.values() for c in lista)
    feitas = 0
    for t in transacoes:
        lista = por_transacao.get(t.pk, [])
        if len(lista) == 1 and procurados[lista[0].chave] == 1:
            _vincular(t, lista[0], usuario)
            feitas += 1
    return feitas


@transaction.atomic
def criar_lancamento(transacao, *, descricao, categoria, pessoa, forma, usuario):
    """A new entry, already paid on the statement date, for a line the system did not know."""
    transacao = _pendente(transacao)
    lancamento = servicos.criar_lancamento(
        clinica=transacao.clinica,
        tipo=Lancamento.Tipo.RECEBER if transacao.entrada else Lancamento.Tipo.PAGAR,
        pessoa=pessoa or descricao,
        descricao=descricao,
        categoria=categoria,
        valor_total=abs(transacao.valor),
        parcelas=1,
        primeiro_vencimento=transacao.data,
        usuario=usuario,
    )
    pagamento = servicos.receber(
        lancamento.parcelas.get(),
        usuario=usuario,
        valor=abs(transacao.valor),
        forma=forma,
        conta=transacao.conta,
        data=transacao.data,
    )
    _vincular(transacao, Candidato(f"p{pagamento.pk}", pagamento.data, "", pagamento), usuario)
    return lancamento


@transaction.atomic
def ignorar(transacao, *, motivo, usuario):
    transacao = _pendente(transacao)
    transacao.situacao = Situacao.IGNORADA
    transacao.motivo = motivo
    transacao.conciliado_por = usuario
    transacao.conciliado_em = timezone.now()
    transacao.save()


@transaction.atomic
def desfazer(transacao):
    """Back to pending. An entry created from the line stays (cancel it if it was wrong)."""
    transacao = TransacaoBancaria.objects.select_for_update().get(pk=transacao.pk)
    transacao.situacao = Situacao.PENDENTE
    transacao.pagamento = None
    transacao.movimento = None
    transacao.motivo = ""
    transacao.conciliado_por = None
    transacao.conciliado_em = None
    transacao.save()


def saldo_no_sistema(importacao):
    """The system's balance of the account on the bank balance date (None without one)."""
    if importacao.saldo is None or importacao.saldo_em is None:
        return None
    for conta, saldo in servicos.saldos_das_contas(ate=importacao.saldo_em):
        if conta.pk == importacao.conta_id:
            return saldo
    return None
