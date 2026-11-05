"""Estimate rules: approving (becomes a receivable) and refusing."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.finance import services as financeiro
from apps.finance.models import Entry

from .models import Estimate


@transaction.atomic
def aprovar(estimate, *, parcelas, primeiro_vencimento, category, user, payment=None):
    """Approve an open estimate: creates the receivable (and, optionally, pays the 1st
    installment with `pagamento` = {"forma": ..., "conta": ...}). Returns the receivable."""
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser aprovado."))
    total = estimate.total
    if total <= 0:
        raise ValidationError(_("O orçamento não tem valor a receber."))
    entry = financeiro.criar_lancamento(
        clinic=estimate.clinic,
        kind=Entry.Tipo.RECEBER,
        patient=estimate.patient,
        practitioner=estimate.practitioner,
        description=_("Orçamento nº %(numero)s") % {"numero": estimate.pk},
        category=category,
        total_amount=total,
        parcelas=parcelas,
        primeiro_vencimento=primeiro_vencimento,
        user=user,
    )
    if payment:
        primeira = entry.parcelas.order_by("number").first()
        financeiro.receber(primeira, user=user, amount=primeira.amount, **payment)
    estimate.status = Estimate.Situacao.APROVADO
    estimate.entry = entry
    estimate.decided_at = timezone.now()
    estimate.decided_by = user
    estimate.save()
    return entry


@transaction.atomic
def recusar(estimate, *, user):
    # Locked like in aprovar(), so approving and refusing at once cannot both succeed.
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Situacao.ABERTO:
        raise ValidationError(_("Só um orçamento em aberto pode ser recusado."))
    estimate.status = Estimate.Situacao.RECUSADO
    estimate.decided_at = timezone.now()
    estimate.decided_by = user
    estimate.save()
