from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel
from apps.core.ordering import ALPHABETICAL
from apps.core.validators import validate_color


class Practitioner(ClinicModel):
    """A practitioner who sees patients (dentist, doctor, physiotherapist...)."""

    name = models.CharField(_("name"), max_length=200, db_collation=ALPHABETICAL)
    registration = models.CharField(
        _("professional license"),
        max_length=30,
        blank=True,
        help_text=_("CRO, CRM, CREFITO, CRP…"),
    )
    color = models.CharField(
        _("schedule color"),
        max_length=7,
        default="#0d6efd",
        validators=[validate_color],
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="practitioners",
        verbose_name=_("login user"),
        help_text=_("Account this practitioner uses to log in (optional)."),
    )
    # Share of what is received on this practitioner's receivables (0.19.0, decision 053).
    commission_percentage = models.DecimalField(
        _("commission (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text=_("Percentage of the amount received on this practitioner's entries."),
    )
    active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "practitioners_practitioner"
        verbose_name = _("practitioner")
        verbose_name_plural = _("practitioners")
        ordering = ["name"]
        indexes = [models.Index(fields=["clinic", "name"], name="practitioner_clinic_name")]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "user"],
                condition=models.Q(user__isnull=False),
                name="practitioner_user_unique_per_clinic",
            ),
        ]

    def __str__(self):
        return self.name
