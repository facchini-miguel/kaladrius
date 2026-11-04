"""Estimate rules: approving (becomes a receivable) and refusing."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.finance import services as financeiro
from apps.finance.models import Entry

from .models import Estimate


@transaction.atomic
def aprovar(orcamento, *, parcelas, primeiro_vencimento, categoria, user, pagamento=None):
    """Approve an open estimate: creates the receivable (and, optionally, pays the 1st
    installment with `pagamento` = {"forma": ..., "conta": ...}). Returns the receivable."""
    orcamento = Estimate.objects.select_for_update().get(pk=orcamento.pk)
    if orcamento.status != Estimate.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser aprovado."))
    total = orcamento.total
    if total <= 0:
        raise ValidationError(_("O orçamento não tem valor a receber."))
    entry = financeiro.criar_lancamento(
        clinic=orcamento.clinic,
        kind=Entry.Tipo.RECEBER,
        patient=orcamento.patient,
        practitioner=orcamento.practitioner,
        description=_("Orçamento nº %(numero)s") % {"numero": orcamento.pk},
        categoria=categoria,
        valor_total=total,
        parcelas=parcelas,
        primeiro_vencimento=primeiro_vencimento,
        user=user,
    )
    if pagamento:
        primeira = entry.parcelas.order_by("number").first()
        financeiro.receber(primeira, user=user, amount=primeira.amount, **pagamento)
    orcamento.status = Estimate.Situacao.APROVADO
    orcamento.entry = entry
    orcamento.decidido_em = timezone.now()
    orcamento.decidido_por = user
    orcamento.save()
    return entry


@transaction.atomic
def recusar(orcamento, *, user):
    # Locked like in aprovar(), so approving and refusing at once cannot both succeed.
    orcamento = Estimate.objects.select_for_update().get(pk=orcamento.pk)
    if orcamento.status != Estimate.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser recusado."))
    orcamento.status = Estimate.Situacao.RECUSADO
    orcamento.decidido_em = timezone.now()
    orcamento.decidido_por = user
    orcamento.save()
