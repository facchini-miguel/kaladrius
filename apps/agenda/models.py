from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ModeloDaClinica, sem_isolamento
from apps.core.validadores import validar_cor
from apps.odontologia.dentes import TIPOS_DE_ATENDIMENTO

# Appointment types a new clinic starts with (decision 080): the dental module's for the
# Odontologia area, these for the others. Each clinic can rename, recolor, deactivate or
# add types.
TIPOS_PADRAO = [
    ("Liberado", "#b9f1a7"),
    ("Consulta", "#e7a5f7"),
    ("Retorno", "#a7eef1"),
    ("Exame", "#f6f7a5"),
    ("Procedimento", "#f7a5a5"),
    ("Atendimento de 15 em 15", "#d5dae6"),
    ("Ocupado", "#a7bef1"),
]


class TipoAtendimento(ModeloDaClinica):
    """Kind of appointment (surgery, first visit...). Its color paints the schedule."""

    nome = models.CharField(_("nome"), max_length=60)
    cor = models.CharField(_("cor"), max_length=7, default="#0d6efd", validators=[validar_cor])
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("tipo de atendimento")
        verbose_name_plural = _("tipos de atendimento")
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

    class Situacao(models.TextChoices):
        """Whether the patient came (0.24.0). Only appointments with a patient are marked."""

        AGENDADO = "agendado", _("Agendado")
        COMPARECEU = "compareceu", _("Compareceu")
        FALTOU = "faltou", _("Faltou")
        # Kept for the history and the no-show figures, but frees the time slot.
        DESMARCOU = "desmarcou", _("Desmarcou")

    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="agendamentos",
        verbose_name=_("profissional"),
    )
    tipo = models.ForeignKey(
        TipoAtendimento,
        on_delete=models.PROTECT,
        related_name="agendamentos",
        verbose_name=_("tipo de atendimento"),
    )
    inicio = models.DateTimeField(_("início"))
    fim = models.DateTimeField(_("fim"))
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agendamentos",
        verbose_name=_("paciente"),
    )
    descricao = models.TextField(_("descrição"), blank=True)
    situacao = models.CharField(
        _("situação"), max_length=10, choices=Situacao.choices, default=Situacao.AGENDADO
    )
    # Appointments created together by "repeat N weeks" share the same series id.
    serie = models.UUIDField(_("série"), null=True, blank=True, editable=False)
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
        verbose_name = _("agendamento")
        verbose_name_plural = _("agendamentos")
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
                # A cancelled appointment does not hold the slot.
                condition=~models.Q(situacao="desmarcou"),
                violation_error_message=_("O profissional já tem um agendamento neste horário."),
            ),
        ]

    def __str__(self):
        return f"{self.titulo} ({timezone.localtime(self.inicio):%d/%m/%Y %H:%M})"

    @property
    def titulo(self):
        if self.paciente_id:
            return self.paciente.nome
        return (self.descricao.strip().splitlines() or [gettext("Horário reservado")])[0]

    @property
    def desmarcado(self):
        return self.situacao == self.Situacao.DESMARCOU

    @property
    def presenca_marcavel(self):
        """Came or missed can be marked from the day of the appointment on."""
        return timezone.localdate(self.inicio) <= timezone.localdate()


def criar_tipos_padrao(clinica):
    """Create the default appointment types for a clinic that has none."""
    with sem_isolamento():
        if TipoAtendimento.objects.filter(clinica=clinica).exists():
            return
        tipos = TIPOS_DE_ATENDIMENTO if clinica.odontologia else TIPOS_PADRAO
        TipoAtendimento.objects.bulk_create(
            TipoAtendimento(clinica=clinica, nome=nome, cor=cor) for nome, cor in tipos
        )
