from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel


class Recall(ClinicModel):
    """A recall: a date to contact a patient again (e.g. six-month check-up)."""

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="recalls",
        verbose_name=_("patient"),
    )
    date = models.DateField(_("date"))
    description = models.CharField(
        _("description"),
        max_length=200,
        help_text=_("E.g.: 6-month check-up."),
    )
    done = models.BooleanField(_("done"), default=False)
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
        db_table = "recalls_recall"
        verbose_name = _("recall")
        verbose_name_plural = _("recalls")
        ordering = ["date", "patient__name"]
        indexes = [models.Index(fields=["clinic", "date"], name="recall_clinic_date")]

    def __str__(self):
        return f"{self.patient} em {self.date:%d/%m/%Y}"
