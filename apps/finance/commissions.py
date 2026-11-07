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

CENT = Decimal("0.01")


def percentage_for(amount, percentage):
    return (amount * percentage / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def _receipts(practitioner):
    return Payment.objects.filter(
        installment__entry__kind=Entry.Kind.RECEIVABLE,
        installment__entry__practitioner=practitioner,
    ).select_related("installment__entry__patient")


def _credits(practitioner, until):
    return _receipts(practitioner).filter(reversed=False, commission__isnull=True, date__lte=until)


def _debits(practitioner):
    """Receipts already commissioned and then reversed, not discounted yet (a few)."""
    debits = list(
        _receipts(practitioner)
        .filter(reversed=True, commission__isnull=False, commission_reversal__isnull=True)
        .select_related("commission")
        .order_by("date", "pk")
    )
    for debit in debits:
        debit.commission_returned = percentage_for(debit.amount, debit.commission.percentage)
    return debits


def pending(practitioner, until):
    """What would be paid to the practitioner for receipts up to `ate`, receipt by receipt."""
    credit_rows = list(_credits(practitioner, until).order_by("date", "pk"))
    debits = _debits(practitioner)
    received_amount = sum((p.amount for p in credit_rows), start=ZERO)
    gross = percentage_for(received_amount, practitioner.commission_percentage)
    reversal_deduction = sum((p.commission_returned for p in debits), start=ZERO)
    return {
        "practitioner": practitioner,
        "credits": credit_rows,
        "debits": debits,
        "received_amount": received_amount,
        "gross": gross,
        "reversal_deduction": reversal_deduction,
        "amount": gross - reversal_deduction,
    }


def summary(until):
    """Pending commission of every practitioner with a percentage or something pending.

    Only the totals, added up by the database: loading every receipt not commissioned yet
    took seconds in a clinic with years of them (volume test, decision 108).
    """
    rows = []
    for practitioner in Practitioner.objects.order_by("-active", "name"):
        totals = _credits(practitioner, until).aggregate(
            received_amount=Sum("amount"), how_many=Count("pk")
        )
        debits = _debits(practitioner)
        if not (practitioner.commission_percentage or totals["how_many"] or debits):
            continue
        received_amount = totals["received_amount"] or ZERO
        gross = percentage_for(received_amount, practitioner.commission_percentage)
        reversal_deduction = sum((p.commission_returned for p in debits), start=ZERO)
        rows.append(
            {
                "practitioner": practitioner,
                "received_amount": received_amount,
                "gross": gross,
                "reversal_deduction": reversal_deduction,
                "amount": gross - reversal_deduction,
            }
        )
    return rows


@transaction.atomic
def pay(practitioner, *, until, due_date, category, user):
    """Create the payable for the pending commission and mark the receipts it covers."""
    # Locking the practitioner serializes two people paying the same commission at once.
    practitioner = Practitioner.objects.select_for_update().get(pk=practitioner.pk)
    calculation = pending(practitioner, until)
    if calculation["amount"] <= 0:
        raise ValidationError(_("There is no commission to pay up to this date."))
    entry = services.create_entry(
        clinic=practitioner.clinic,
        kind=Entry.Kind.PAYABLE,
        payer=practitioner.name,
        practitioner=practitioner,
        description=_("Commission of %(name)s up to %(date)s")
        % {"name": practitioner.name, "date": date_format(until, "SHORT_DATE_FORMAT")},
        category=category,
        total_amount=calculation["amount"],
        installments=1,
        first_due_date=due_date,
        user=user,
    )
    commission = Commission.objects.create(
        clinic=practitioner.clinic,
        practitioner=practitioner,
        until=until,
        percentage=practitioner.commission_percentage,
        received_amount=calculation["received_amount"],
        reversal_deduction=calculation["reversal_deduction"],
        amount=calculation["amount"],
        entry=entry,
        created_by=user,
    )
    # One by one (not .update()), so the audit log records which receipts it covered.
    for payment in calculation["credits"]:
        payment.commission = commission
        payment.save(update_fields=["commission"])
    for payment in calculation["debits"]:
        payment.commission_reversal = commission
        payment.save(update_fields=["commission_reversal"])
    return commission


def release(commission):
    """Undo a commission whose payable was cancelled: its receipts become pending again.

    Refused while a later commission deducted the reversal of one of its receipts: that
    deduction only makes sense if this one was paid, so the later one is cancelled first.
    """
    deducted = (
        Commission.objects.filter(
            cancelled=False,
            reversed_payments__commission=commission,
        )
        .exclude(pk=commission.pk)
        .order_by("until")
        .first()
    )
    if deducted is not None:
        raise ValidationError(
            _(
                "This commission cannot be cancelled: the reversal of one of its receipts was "
                "already deducted in the commission up to %(date)s. Cancel that one first."
            )
            % {"date": date_format(deducted.until, "SHORT_DATE_FORMAT")}
        )
    # One by one (not .update()), so the audit log records each change.
    for payment in Payment.objects.filter(commission=commission):
        payment.commission = None
        payment.save(update_fields=["commission"])
    for payment in Payment.objects.filter(commission_reversal=commission):
        payment.commission_reversal = None
        payment.save(update_fields=["commission_reversal"])
    commission.cancelled = True
    commission.save(update_fields=["cancelled"])
