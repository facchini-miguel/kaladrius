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

    name = models.CharField(_("nome"), max_length=120, db_collation=ALPHABETICAL)
    # In the country's procedure coding: TUSS, CDT, ADA item number... (decision 125).
    code = models.CharField(_("código"), max_length=20, blank=True)
    amount = models.DecimalField(_("valor"), **MONEY)
    category = models.ForeignKey(
        "financeiro.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("categoria"),
        help_text=_("Categoria de receita usada quando o orçamento é aprovado."),
    )
    active = models.BooleanField(_("ativo"), default=True)

    class Meta:
        db_table = "estimates_procedure"
        verbose_name = _("procedimento")
        verbose_name_plural = _("procedimentos")
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
        OPEN = "aberto", pgettext_lazy("orçamento", "Em aberto")
        APPROVED = "aprovado", _("Aprovado")
        REFUSED = "recusado", _("Recusado")

    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        related_name="estimates",
        verbose_name=_("paciente"),
    )
    practitioner = models.ForeignKey(
        "profissionais.Practitioner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("profissional"),
    )
    date = models.DateField(_("data"), default=timezone.localdate)
    valid_until = models.DateField(_("válido até"), default=default_valid_until)
    status = models.CharField(
        _("situação"),
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    discount = models.DecimalField(_("desconto"), default=Decimal("0.00"), **MONEY)
    notes = models.TextField(_("observações"), blank=True)
    entry = models.OneToOneField(
        "financeiro.Entry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate",
        verbose_name=_("lançamento a receber"),
    )
    decided_at = models.DateTimeField(_("aprovado ou recusado em"), null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("aprovado ou recusado por"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "estimates_estimate"
        verbose_name = _("orçamento")
        verbose_name_plural = _("orçamentos")
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
        return sorted({dente for item in self.items.all() for dente in item.teeth_list})


class EstimateItem(ClinicModel):
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("orçamento"),
    )
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("procedimento"),
    )
    description = models.CharField(_("descrição"), max_length=200)
    code = models.CharField(_("código"), max_length=20, blank=True)  # copied, like descricao
    # FDI tooth numbers separated by commas ("11,12"); empty for the whole mouth.
    teeth = models.CharField(_("dentes"), max_length=200, blank=True)
    faces = models.CharField(
        _("faces ou região"),
        max_length=60,
        blank=True,
        help_text=_("Ex.: MOD, vestibular, arcada superior."),
    )
    quantity = models.PositiveSmallIntegerField(_("quantidade"), default=1)
    unit_price = models.DecimalField(_("valor unitário"), **MONEY)

    class Meta:
        db_table = "estimates_estimate_item"
        verbose_name = _("item do orçamento")
        verbose_name_plural = _("itens do orçamento")
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
        liberado = getattr(self, "odontologia_desligada_liberada", False)
        if dental and not clinic.dentistry and not liberado:
            raise ValidationError(_("Habilite Odontologia para alterar itens com dentes ou faces."))

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
