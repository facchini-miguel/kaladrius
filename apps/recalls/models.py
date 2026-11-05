from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel


class Recall(ClinicModel):
    """A recall: a date to contact a patient again (e.g. six-month check-up)."""

    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        related_name="rechamadas",
        verbose_name=_("paciente"),
    )
    date = models.DateField(_("data"))
    description = models.CharField(
        _("descrição"),
        max_length=200,
        help_text=_("Ex.: revisão de 6 meses."),
    )
    done = models.BooleanField(_("concluída"), default=False)
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
        db_table = "recalls_recall"
        verbose_name = _("rechamada")
        verbose_name_plural = _("rechamadas")
        ordering = ["date", "patient__name"]
        indexes = [models.Index(fields=["clinic", "date"], name="recall_clinic_date")]

    def __str__(self):
        return f"{self.patient} em {self.date:%d/%m/%Y}"
