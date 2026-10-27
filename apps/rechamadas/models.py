from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ModeloDaClinica


class Rechamada(ModeloDaClinica):
    """A recall: a date to contact a patient again (e.g. six-month check-up)."""

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        related_name="rechamadas",
        verbose_name=_("paciente"),
    )
    data = models.DateField(_("data"))
    descricao = models.CharField(
        _("descrição"), max_length=200, help_text=_("Ex.: revisão de 6 meses.")
    )
    concluida = models.BooleanField(_("concluída"), default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("rechamada")
        verbose_name_plural = _("rechamadas")
        ordering = ["data", "paciente__nome"]
        indexes = [models.Index(fields=["clinica", "data"], name="rechamada_clinica_data")]

    def __str__(self):
        return f"{self.paciente} em {self.data:%d/%m/%Y}"
