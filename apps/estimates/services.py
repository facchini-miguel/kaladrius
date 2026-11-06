"""Estimate rules: approving (becomes a receivable) and refusing."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.finance import services as finance_services
from apps.finance.models import Entry

from .models import Estimate


@transaction.atomic
def approve(estimate, *, installments, first_due_date, category, user, payment=None):
    """Approve an open estimate: creates the receivable (and, optionally, pays the 1st
    installment with `pagamento` = {"forma": ..., "conta": ...}). Returns the receivable."""
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Status.OPEN:
        raise ValidationError(_("Só um orçamento em aberto pode ser aprovado."))
    total = estimate.total
    if total <= 0:
        raise ValidationError(_("O orçamento não tem valor a receber."))
    entry = finance_services.create_entry(
        clinic=estimate.clinic,
        kind=Entry.Kind.RECEIVABLE,
        patient=estimate.patient,
        practitioner=estimate.practitioner,
        description=_("Orçamento nº %(numero)s") % {"numero": estimate.pk},
        category=category,
        total_amount=total,
        installments=installments,
        first_due_date=first_due_date,
        user=user,
    )
    if payment:
        first = entry.installments.order_by("number").first()
        finance_services.receive(first, user=user, amount=first.amount, **payment)
    estimate.status = Estimate.Status.APPROVED
    estimate.entry = entry
    estimate.decided_at = timezone.now()
    estimate.decided_by = user
    estimate.save()
    return entry


@transaction.atomic
def refuse(estimate, *, user):
    # Locked like in aprovar(), so approving and refusing at once cannot both succeed.
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Status.OPEN:
        raise ValidationError(_("Só um orçamento em aberto pode ser recusado."))
    estimate.status = Estimate.Status.REFUSED
    estimate.decided_at = timezone.now()
    estimate.decided_by = user
    estimate.save()
