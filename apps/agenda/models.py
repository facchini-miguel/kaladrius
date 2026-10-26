from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.utils import timezone

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


class TsTzRange(models.Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Agendamento(ModeloDaClinica):
    """An appointment in a practitioner's schedule."""

    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="agendamentos",
        verbose_name="profissional",
    )
    tipo = models.ForeignKey(
        TipoAtendimento,
        on_delete=models.PROTECT,
        related_name="agendamentos",
        verbose_name="tipo de atendimento",
    )
    inicio = models.DateTimeField("início")
    fim = models.DateTimeField("fim")
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agendamentos",
        verbose_name="paciente",
    )
    descricao = models.TextField("descrição", blank=True)
    # Appointments created together by "repeat N weeks" share the same series id.
    serie = models.UUIDField("série", null=True, blank=True, editable=False)
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
        verbose_name = "agendamento"
        verbose_name_plural = "agendamentos"
        ordering = ["inicio"]
        indexes = [
            models.Index(
                fields=["clinica", "profissional", "inicio"], name="agendamento_prof_inicio"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(inicio__lt=models.F("fim")),
                name="agendamento_inicio_antes_do_fim",
            ),
            # Last line of defense against double booking, even under concurrent requests.
            ExclusionConstraint(
                name="agendamento_sem_sobreposicao",
                expressions=[
                    (TsTzRange("inicio", "fim", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("profissional", RangeOperators.EQUAL),
                ],
                violation_error_message="O profissional já tem um agendamento neste horário.",
            ),
        ]

    def __str__(self):
        return f"{self.titulo} ({timezone.localtime(self.inicio):%d/%m/%Y %H:%M})"

    @property
    def titulo(self):
        if self.paciente_id:
            return self.paciente.nome
        return (self.descricao.strip().splitlines() or ["Horário reservado"])[0]


def criar_tipos_padrao(clinica):
    """Create the default appointment types for a clinic that has none."""
    with sem_isolamento():
        if TipoAtendimento.objects.filter(clinica=clinica).exists():
            return
        TipoAtendimento.objects.bulk_create(
            TipoAtendimento(clinica=clinica, nome=nome, cor=cor) for nome, cor in TIPOS_PADRAO
        )
