"""Procedure price list and treatment estimates (0.18.0).

An estimate (Orcamento) lists procedures for a patient, optionally per tooth (FDI
numbering, picked on a clickable dental chart). When the patient approves it, it becomes a
receivable (financeiro.Lancamento) in the chosen installments.
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.isolation import ClinicModel, WrongClinic
from apps.core.models import Clinic
from apps.core.ordering import ALPHABETICAL

MONEY = {"max_digits": 12, "decimal_places": 2}
DEFAULT_VALIDITY = 30  # days


def default_valid_until():
    return timezone.localdate() + datetime.timedelta(days=DEFAULT_VALIDITY)


# The old name stays: the migrations that created the field reference it (decision 176).
validade_padrao = default_valid_until


class Procedure(ClinicModel):
    """An item of the clinic's price list (cleaning, filling, root canal...)."""

    name = models.CharField(_("name"), max_length=120, db_collation=ALPHABETICAL)
    # In the country's procedure coding: TUSS, CDT, ADA item number... (decision 125).
    code = models.CharField(_("code"), max_length=20, blank=True)
    amount = models.DecimalField(_("amount"), **MONEY)
    category = models.ForeignKey(
        "finance.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("category"),
        help_text=_("Income category used when the estimate is approved."),
    )
    active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "estimates_procedure"
        verbose_name = _("procedure")
        verbose_name_plural = _("procedures")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="procedure_unique"),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="procedure_amount_not_negative"
            ),
        ]

    def __str__(self):
        return self.name


class Estimate(ClinicModel):
    class Status(models.TextChoices):
        OPEN = "open", pgettext_lazy("estimate", "Open")
        APPROVED = "approved", _("Approved")
        REFUSED = "refused", _("Refused")

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="estimates",
        verbose_name=_("patient"),
    )
    practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    date = models.DateField(_("date"), default=timezone.localdate)
    valid_until = models.DateField(_("valid until"), default=default_valid_until)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    discount = models.DecimalField(_("discount"), default=Decimal("0.00"), **MONEY)
    notes = models.TextField(_("notes"), blank=True)
    entry = models.OneToOneField(
        "finance.Entry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate",
        verbose_name=_("receivable"),
    )
    decided_at = models.DateTimeField(_("approved or refused at"), null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("approved or refused by"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "estimates_estimate"
        verbose_name = _("estimate")
        verbose_name_plural = _("estimates")
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(discount__gte=0), name="estimate_discount_not_negative"
            ),
        ]

    def __str__(self):
        return f"{self.pk} – {self.patient}"

    @property
    def subtotal(self):
        return sum((item.total for item in self.items.all()), start=Decimal("0.00"))

    @property
    def total(self):
        return max(self.subtotal - self.discount, Decimal("0.00"))

    @property
    def is_expired(self):
        return self.status == self.Status.OPEN and self.valid_until < timezone.localdate()

    @property
    def teeth(self):
        """Every tooth in the estimate, for the dental chart."""
        return sorted({tooth for item in self.items.all() for tooth in item.teeth_list})


class EstimateItem(ClinicModel):
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("estimate"),
    )
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("procedure"),
    )
    description = models.CharField(_("description"), max_length=200)
    code = models.CharField(_("code"), max_length=20, blank=True)  # copied, like descricao
    # FDI tooth numbers separated by commas ("11,12"); empty for the whole mouth.
    teeth = models.CharField(_("teeth"), max_length=200, blank=True)
    faces = models.CharField(
        _("surfaces or region"),
        max_length=60,
        blank=True,
        help_text=_("E.g.: MOD, buccal, upper arch."),
    )
    quantity = models.PositiveSmallIntegerField(_("quantity"), default=1)
    unit_price = models.DecimalField(_("unit price"), **MONEY)

    class Meta:
        db_table = "estimates_estimate_item"
        verbose_name = _("estimate item")
        verbose_name_plural = _("estimate items")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="estimate_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0), name="estimate_item_price_not_negative"
            ),
        ]

    def __str__(self):
        return self.description

    def _check_module(self):
        self._check_clinic()
        if self.estimate.clinic_id != self.clinic_id:
            raise WrongClinic("The estimate belongs to another clinic.")
        clinic = Clinic.objects.select_for_update().get(pk=self.clinic_id)
        previous = (
            type(self).objects.filter(pk=self.pk).values("teeth", "faces").first()
            if self.pk is not None
            else None
        )
        dental = self.teeth or self.faces or (previous and any(previous.values()))
        # The view sets the flag only for the system administrator (decision 115).
        allowed = getattr(self, "dentistry_off_allowed", False)
        if dental and not clinic.dentistry and not allowed:
            raise ValidationError(_("Enable Dentistry to change items with teeth or surfaces."))

    @transaction.atomic
    def save(self, *args, **kwargs):
        self._check_module()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        self._check_module()
        return super().delete(*args, **kwargs)

    @property
    def total(self):
        return self.unit_price * self.quantity

    @property
    def teeth_display(self):
        """In the clinic's numbering (decision 122): "18, 36" in FDI, "1, 19" in Universal."""
        from apps.dentistry.teeth import name, sort_teeth

        return ", ".join(name(d) for d in sort_teeth(self.teeth_list))

    @property
    def teeth_list(self):
        return [int(d) for d in self.teeth.split(",") if d.strip().isdecimal()]
