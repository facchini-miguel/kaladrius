"""Financial rules: installments, receiving, reversing, cancelling and debtors."""

import calendar
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import ZERO, Lancamento, Pagamento, Parcela

CENTAVO = Decimal("0.01")
# Days overdue for the debtors report: up to 30, 31-60, 61-90, over 90.
FAIXAS_DE_ATRASO = [30, 60, 90]


def dividir(total, quantidade):
    """Equal installments; the leftover cents go to the first one."""
    base = (total / quantidade).quantize(CENTAVO, rounding=ROUND_DOWN)
    valores = [base] * quantidade
    valores[0] += total - base * quantidade
    return valores


def somar_meses(data, meses):
    """Same day N months later (the 31st becomes the last day of shorter months)."""
    ano, mes = divmod(data.month - 1 + meses, 12)
    ano, mes = data.year + ano, mes + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


@transaction.atomic
def criar_lancamento(*, parcelas, primeiro_vencimento, usuario, **campos):
    """Create an entry with `parcelas` monthly installments from `primeiro_vencimento`."""
    lancamento = Lancamento.objects.create(criado_por=usuario, **campos)
    Parcela.objects.bulk_create(
        Parcela(
            clinica=lancamento.clinica,
            lancamento=lancamento,
            numero=numero,
            vencimento=somar_meses(primeiro_vencimento, numero - 1),
            valor=valor,
        )
        for numero, valor in enumerate(dividir(lancamento.valor_total, parcelas), start=1)
    )
    return lancamento


@transaction.atomic
def receber(parcela, *, usuario, **campos):
    """Record a payment for an installment. Raises ValidationError if it exceeds the balance.

    The installment row is locked, so two people receiving at once cannot overpay it.
    """
    parcela = Parcela.objects.select_for_update().select_related("lancamento").get(pk=parcela.pk)
    if parcela.lancamento.cancelado:
        raise ValidationError(_("Este lançamento foi cancelado."))
    pagamento = Pagamento(clinica=parcela.clinica, parcela=parcela, criado_por=usuario, **campos)
    _pago, saldo = parcela.valores()
    if pagamento.principal <= 0:
        raise ValidationError(_("O valor abatido da parcela precisa ser maior que zero."))
    if pagamento.principal > saldo:
        raise ValidationError(
            _("O valor abatido (%(abatido)s) passa do que falta na parcela (%(saldo)s).")
            % {"abatido": pagamento.principal, "saldo": saldo}
        )
    pagamento.save()
    return pagamento


@transaction.atomic
def estornar(pagamento, *, motivo, usuario):
    pagamento.estornado = True
    pagamento.estornado_em = timezone.now()
    pagamento.estornado_por = usuario
    pagamento.motivo_estorno = motivo
    pagamento.save()


@transaction.atomic
def cancelar(lancamento, *, motivo, usuario):
    """Cancel an entry. Payments must be reversed first (they are real money)."""
    if Pagamento.objects.filter(parcela__lancamento=lancamento, estornado=False).exists():
        raise ValidationError(
            _("Este lançamento tem pagamentos. Estorne os pagamentos antes de cancelar.")
        )
    lancamento.cancelado = True
    lancamento.cancelado_em = timezone.now()
    lancamento.cancelado_por = usuario
    lancamento.motivo_cancelamento = motivo
    lancamento.save()


def situacao(parcela, hoje=None):
    """Status of an installment annotated with com_saldo() (code, label)."""
    hoje = hoje or timezone.localdate()
    if parcela.lancamento.cancelado:
        return "cancelada", _("Cancelada")
    if parcela.saldo <= 0:
        return "paga", _("Paga")
    if parcela.vencimento < hoje:
        return "vencida", _("Vencida")
    if parcela.pago > 0:
        return "parcial", _("Paga em parte")
    return "aberta", _("Em aberto")


def devedores(hoje=None):
    """Who owes the clinic, from the open installments of receivables.

    One row per patient (or payer name): overdue total split by days late, amount not yet
    due and the oldest due date, ordered by the overdue total.
    """
    hoje = hoje or timezone.localdate()
    parcelas = (
        Parcela.objects.abertas()
        .filter(lancamento__tipo=Lancamento.Tipo.RECEBER)
        .select_related("lancamento__paciente")
    )
    linhas = defaultdict(
        lambda: {
            "paciente": None,
            "nome": "",
            "faixas": [ZERO] * (len(FAIXAS_DE_ATRASO) + 1),
            "vencido": ZERO,
            "a_vencer": ZERO,
            "mais_antigo": None,
        }
    )
    for parcela in parcelas:
        lancamento = parcela.lancamento
        chave = (
            ("paciente", lancamento.paciente_id)
            if lancamento.paciente_id
            else (
                "pessoa",
                lancamento.pessoa.strip().lower(),
            )
        )
        linha = linhas[chave]
        linha["paciente"] = lancamento.paciente
        linha["nome"] = lancamento.nome_pessoa
        if parcela.vencimento >= hoje:
            linha["a_vencer"] += parcela.saldo
            continue
        atraso = (hoje - parcela.vencimento).days
        faixa = next(
            (i for i, limite in enumerate(FAIXAS_DE_ATRASO) if atraso <= limite),
            len(FAIXAS_DE_ATRASO),
        )
        linha["faixas"][faixa] += parcela.saldo
        linha["vencido"] += parcela.saldo
        if linha["mais_antigo"] is None or parcela.vencimento < linha["mais_antigo"]:
            linha["mais_antigo"] = parcela.vencimento
    resultado = [linha for linha in linhas.values() if linha["vencido"] or linha["a_vencer"]]
    return sorted(resultado, key=lambda linha: (-linha["vencido"], linha["nome"]))


def resumo_do_paciente(paciente, hoje=None):
    """Open installments, totals and latest payments of a patient (for the record)."""
    hoje = hoje or timezone.localdate()
    abertas = list(
        Parcela.objects.abertas()
        .filter(lancamento__paciente=paciente, lancamento__tipo=Lancamento.Tipo.RECEBER)
        .select_related("lancamento")
        .order_by("vencimento")
    )
    return {
        "abertas": abertas,
        "vencido": sum((p.saldo for p in abertas if p.vencimento < hoje), start=ZERO),
        "a_vencer": sum((p.saldo for p in abertas if p.vencimento >= hoje), start=ZERO),
        "pagamentos": list(
            Pagamento.objects.filter(parcela__lancamento__paciente=paciente)
            .select_related("parcela__lancamento", "conta")
            .order_by("-data", "-pk")[:5]
        ),
    }
