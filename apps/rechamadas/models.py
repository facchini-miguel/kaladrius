from django.conf import settings
from django.db import models

from apps.core.isolamento import ModeloDaClinica


class Rechamada(ModeloDaClinica):
    """A recall: a date to contact a patient again (e.g. six-month check-up)."""

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        related_name="rechamadas",
        verbose_name="paciente",
    )
    data = models.DateField("data")
    descricao = models.CharField("descrição", max_length=200, help_text="Ex.: revisão de 6 meses.")
    concluida = models.BooleanField("concluída", default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="criado por",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    alterado_em = models.DateTimeField("alterado em", auto_now=True)

    class Meta:
        verbose_name = "rechamada"
        verbose_name_plural = "rechamadas"
        ordering = ["data", "paciente__nome"]
        indexes = [models.Index(fields=["clinica", "data"], name="rechamada_clinica_data")]

    def __str__(self):
        return f"{self.paciente} em {self.data:%d/%m/%Y}"
