from django.db import models

from apps.core.isolamento import ModeloDaClinica, sem_isolamento
from apps.core.validadores import validar_cor

# Appointment types every new clinic starts with: the ones from the legacy system,
# with the same colors. Each clinic can rename, recolor, deactivate or add types.
TIPOS_PADRAO = [
    ("Liberado", "#b9f1a7"),
    ("Cirurgia", "#f7a5a5"),
    ("Dentística", "#f6f7a5"),
    ("Periodontia", "#7b88cb"),
    ("Consulta inicial", "#e7a5f7"),
    ("Prótese", "#fed27d"),
    ("Endodontia", "#e96cd9"),
    ("Ortodontia", "#a7eef1"),
    ("Atendimento de 15 em 15", "#d5dae6"),
    ("Ocupado", "#a7bef1"),
]


class TipoAtendimento(ModeloDaClinica):
    """Kind of appointment (surgery, first visit...). Its color paints the schedule."""

    nome = models.CharField("nome", max_length=60)
    cor = models.CharField("cor", max_length=7, default="#0d6efd", validators=[validar_cor])
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        verbose_name = "tipo de atendimento"
        verbose_name_plural = "tipos de atendimento"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "nome"], name="tipo_atendimento_unico"),
        ]

    def __str__(self):
        return self.nome


def criar_tipos_padrao(clinica):
    """Create the default appointment types for a clinic that has none."""
    with sem_isolamento():
        if TipoAtendimento.objects.filter(clinica=clinica).exists():
            return
        TipoAtendimento.objects.bulk_create(
            TipoAtendimento(clinica=clinica, nome=nome, cor=cor) for nome, cor in TIPOS_PADRAO
        )
