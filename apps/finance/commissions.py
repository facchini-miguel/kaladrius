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

from apps.practitioners.models import Practitioner

from . import services
from .models import ZERO, Commission, Entry, Payment

CENTAVO = Decimal("0.01")


def percentual_de(amount, percentual):
    return (amount * percentual / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _recebimentos(practitioner):
    return Payment.objects.filter(
        parcela__entry__kind=Entry.Tipo.RECEBER,
        parcela__entry__practitioner=practitioner,
    ).select_related("parcela__entry__patient")


def _creditos(practitioner, until):
    return _recebimentos(practitioner).filter(
        estornado=False, comissao__isnull=True, date__lte=until
    )


def _debitos(practitioner):
    """Receipts already commissioned and then reversed, not discounted yet (a few)."""
    debitos = list(
        _recebimentos(practitioner)
        .filter(estornado=True, comissao__isnull=False, comissao_estorno__isnull=True)
        .select_related("comissao")
        .order_by("date", "pk")
    )
    for debito in debitos:
        debito.comissao_devolvida = percentual_de(debito.amount, debito.comissao.percentual)
    return debitos


def pendente(practitioner, until):
    """What would be paid to the practitioner for receipts up to `ate`, receipt by receipt."""
    creditos = list(_creditos(practitioner, until).order_by("date", "pk"))
    debitos = _debitos(practitioner)
    recebido = sum((p.amount for p in creditos), start=ZERO)
    bruta = percentual_de(recebido, practitioner.comissao_percentual)
    estornos = sum((p.comissao_devolvida for p in debitos), start=ZERO)
    return {
        "practitioner": practitioner,
        "creditos": creditos,
        "debitos": debitos,
        "recebido": recebido,
        "bruta": bruta,
        "estornos": estornos,
        "amount": bruta - estornos,
    }


def resumo(until):
    """Pending commission of every practitioner with a percentage or something pending.

    Only the totals, added up by the database: loading every receipt not commissioned yet
    took seconds in a clinic with years of them (volume test, decision 108).
    """
    linhas = []
    for practitioner in Practitioner.objects.order_by("-active", "name"):
        totais = _creditos(practitioner, until).aggregate(
            recebido=Sum("amount"), quantos=Count("pk")
        )
        debitos = _debitos(practitioner)
        if not (practitioner.comissao_percentual or totais["quantos"] or debitos):
            continue
        recebido = totais["recebido"] or ZERO
        bruta = percentual_de(recebido, practitioner.comissao_percentual)
        estornos = sum((p.comissao_devolvida for p in debitos), start=ZERO)
        linhas.append(
            {
                "practitioner": practitioner,
                "recebido": recebido,
                "bruta": bruta,
                "estornos": estornos,
                "amount": bruta - estornos,
            }
        )
    return linhas


@transaction.atomic
def pagar(practitioner, *, until, vencimento, category, user):
    """Create the payable for the pending commission and mark the receipts it covers."""
    # Locking the practitioner serializes two people paying the same commission at once.
    practitioner = Practitioner.objects.select_for_update().get(pk=practitioner.pk)
    calculo = pendente(practitioner, until)
    if calculo["amount"] <= 0:
        raise ValidationError(_("Não há comissão a pagar até esta data."))
    entry = services.criar_lancamento(
        clinic=practitioner.clinic,
        kind=Entry.Tipo.PAGAR,
        pessoa=practitioner.name,
        practitioner=practitioner,
        description=_("Comissão de %(nome)s até %(data)s")
        % {"nome": practitioner.name, "data": date_format(until, "SHORT_DATE_FORMAT")},
        category=category,
        valor_total=calculo["amount"],
        parcelas=1,
        primeiro_vencimento=vencimento,
        user=user,
    )
    comissao = Commission.objects.create(
        clinic=practitioner.clinic,
        practitioner=practitioner,
        until=until,
        percentual=practitioner.comissao_percentual,
        recebido=calculo["recebido"],
        estornos=calculo["estornos"],
        amount=calculo["amount"],
        entry=entry,
        created_by=user,
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
        Commission.objects.filter(
            cancelada=False,
            pagamentos_estornados__comissao=comissao,
        )
        .exclude(pk=comissao.pk)
        .order_by("until")
        .first()
    )
    if descontou is not None:
        raise ValidationError(
            _(
                "Esta comissão não pode ser cancelada: o estorno de um recebimento dela já foi "
                "descontado na comissão até %(data)s. Cancele aquela antes."
            )
            % {"data": date_format(descontou.until, "SHORT_DATE_FORMAT")}
        )
    # One by one (not .update()), so the audit log records each change.
    for pagamento in Payment.objects.filter(comissao=comissao):
        pagamento.comissao = None
        pagamento.save(update_fields=["comissao"])
    for pagamento in Payment.objects.filter(comissao_estorno=comissao):
        pagamento.comissao_estorno = None
        pagamento.save(update_fields=["comissao_estorno"])
    comissao.cancelada = True
    comissao.save(update_fields=["cancelada"])
