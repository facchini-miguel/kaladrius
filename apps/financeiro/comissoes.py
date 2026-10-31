"""Practitioner commission (0.19.0, decision 053).

The commission is a percentage per practitioner of the money received (Pagamento.valor,
after discounts and including late fees) on receivables that name that practitioner.
Paying it marks the receipts it covered, so none is paid twice; a receipt reversed after
being paid out is deducted from the next commission at the percentage it was paid with.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from apps.profissionais.models import Profissional

from . import servicos
from .models import ZERO, Comissao, Lancamento, Pagamento

CENTAVO = Decimal("0.01")


def percentual_de(valor, percentual):
    return (valor * percentual / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _recebimentos(profissional):
    return Pagamento.objects.filter(
        parcela__lancamento__tipo=Lancamento.Tipo.RECEBER,
        parcela__lancamento__profissional=profissional,
    ).select_related("parcela__lancamento__paciente")


def _creditos(profissional, ate):
    return _recebimentos(profissional).filter(estornado=False, comissao__isnull=True, data__lte=ate)


def _debitos(profissional):
    """Receipts already commissioned and then reversed, not discounted yet (a few)."""
    debitos = list(
        _recebimentos(profissional)
        .filter(estornado=True, comissao__isnull=False, comissao_estorno__isnull=True)
        .select_related("comissao")
        .order_by("data", "pk")
    )
    for debito in debitos:
        debito.comissao_devolvida = percentual_de(debito.valor, debito.comissao.percentual)
    return debitos


def pendente(profissional, ate):
    """What would be paid to the practitioner for receipts up to `ate`, receipt by receipt."""
    creditos = list(_creditos(profissional, ate).order_by("data", "pk"))
    debitos = _debitos(profissional)
    recebido = sum((p.valor for p in creditos), start=ZERO)
    bruta = percentual_de(recebido, profissional.comissao_percentual)
    estornos = sum((p.comissao_devolvida for p in debitos), start=ZERO)
    return {
        "profissional": profissional,
        "creditos": creditos,
        "debitos": debitos,
        "recebido": recebido,
        "bruta": bruta,
        "estornos": estornos,
        "valor": bruta - estornos,
    }


def resumo(ate):
    """Pending commission of every practitioner with a percentage or something pending.

    Only the totals, added up by the database: loading every receipt not commissioned yet
    took seconds in a clinic with years of them (volume test, decision 108).
    """
    linhas = []
    for profissional in Profissional.objects.order_by("-ativo", "nome"):
        totais = _creditos(profissional, ate).aggregate(recebido=Sum("valor"), quantos=Count("pk"))
        debitos = _debitos(profissional)
        if not (profissional.comissao_percentual or totais["quantos"] or debitos):
            continue
        recebido = totais["recebido"] or ZERO
        bruta = percentual_de(recebido, profissional.comissao_percentual)
        estornos = sum((p.comissao_devolvida for p in debitos), start=ZERO)
        linhas.append(
            {
                "profissional": profissional,
                "recebido": recebido,
                "bruta": bruta,
                "estornos": estornos,
                "valor": bruta - estornos,
            }
        )
    return linhas


@transaction.atomic
def pagar(profissional, *, ate, vencimento, categoria, usuario):
    """Create the payable for the pending commission and mark the receipts it covers."""
    # Locking the practitioner serializes two people paying the same commission at once.
    profissional = Profissional.objects.select_for_update().get(pk=profissional.pk)
    calculo = pendente(profissional, ate)
    if calculo["valor"] <= 0:
        raise ValidationError(_("Não há comissão a pagar até esta data."))
    lancamento = servicos.criar_lancamento(
        clinica=profissional.clinica,
        tipo=Lancamento.Tipo.PAGAR,
        pessoa=profissional.nome,
        profissional=profissional,
        descricao=_("Comissão de %(nome)s até %(data)s")
        % {"nome": profissional.nome, "data": date_format(ate, "SHORT_DATE_FORMAT")},
        categoria=categoria,
        valor_total=calculo["valor"],
        parcelas=1,
        primeiro_vencimento=vencimento,
        usuario=usuario,
    )
    comissao = Comissao.objects.create(
        clinica=profissional.clinica,
        profissional=profissional,
        ate=ate,
        percentual=profissional.comissao_percentual,
        recebido=calculo["recebido"],
        estornos=calculo["estornos"],
        valor=calculo["valor"],
        lancamento=lancamento,
        criado_por=usuario,
    )
    # One by one (not .update()), so the audit log records which receipts it covered.
    for pagamento in calculo["creditos"]:
        pagamento.comissao = comissao
        pagamento.save(update_fields=["comissao"])
    for pagamento in calculo["debitos"]:
        pagamento.comissao_estorno = comissao
        pagamento.save(update_fields=["comissao_estorno"])
    return comissao


def liberar(comissao):
    """Undo a commission whose payable was cancelled: its receipts become pending again.

    Refused while a later commission deducted the reversal of one of its receipts: that
    deduction only makes sense if this one was paid, so the later one is cancelled first.
    """
    descontou = (
        Comissao.objects.filter(
            cancelada=False,
            pagamentos_estornados__comissao=comissao,
        )
        .exclude(pk=comissao.pk)
        .order_by("ate")
        .first()
    )
    if descontou is not None:
        raise ValidationError(
            _(
                "Esta comissão não pode ser cancelada: o estorno de um recebimento dela já foi "
                "descontado na comissão até %(data)s. Cancele aquela antes."
            )
            % {"data": date_format(descontou.ate, "SHORT_DATE_FORMAT")}
        )
    # One by one (not .update()), so the audit log records each change.
    for pagamento in Pagamento.objects.filter(comissao=comissao):
        pagamento.comissao = None
        pagamento.save(update_fields=["comissao"])
    for pagamento in Pagamento.objects.filter(comissao_estorno=comissao):
        pagamento.comissao_estorno = None
        pagamento.save(update_fields=["comissao_estorno"])
    comissao.cancelada = True
    comissao.save(update_fields=["cancelada"])
