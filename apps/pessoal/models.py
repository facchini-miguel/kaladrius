"""Staff, salaries and the month's pay (decision 099, legacy Medical planocontas).

The clinic keeps the record and turns each month's pay into a payable. Payroll taxes and
benefits (INSS, FGTS, 13th salary, vacations) stay with the accountant.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ClinicaDiferente, ModeloDaClinica

DINHEIRO = {"max_digits": 12, "decimal_places": 2}
CENTAVO = Decimal("0.01")
# Monthly hours of a 44-hour week (CLT) and the minimum overtime rate (+50%).
HORAS_POR_MES = Decimal(220)
ADICIONAL_HORA_EXTRA = Decimal("1.5")
DIAS_POR_MES = Decimal(30)


class Funcionario(ModeloDaClinica):
    nome = models.CharField(_("nome"), max_length=200)
    cpf = models.CharField(_("CPF"), max_length=11, blank=True)
    cargo = models.CharField(_("cargo"), max_length=100, blank=True)
    admissao = models.DateField(_("admissão"), null=True, blank=True)
    desligamento = models.DateField(_("desligamento"), null=True, blank=True)
    telefone = models.CharField(_("telefone"), max_length=11, blank=True)
    observacoes = models.TextField(_("observações"), blank=True)
    ativo = models.BooleanField(_("ativo"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("funcionário")
        verbose_name_plural = _("funcionários")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "cpf"],
                condition=~Q(cpf=""),
                name="funcionario_cpf_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.nome

    def salario_em(self, data):
        """The salary in force on `data` (the newest one starting on or before it)."""
        salario = self.salarios.filter(desde__lte=data).order_by("-desde", "-pk").first()
        return salario.valor if salario else None


class Salario(ModeloDaClinica):
    """One salary change: the history the legacy kept in salario_fixo_hist."""

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="salarios",
        verbose_name=_("funcionário"),
    )
    valor = models.DecimalField(_("salário"), **DINHEIRO)
    desde = models.DateField(_("desde"))
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("salário")
        verbose_name_plural = _("salários")
        ordering = ["-desde", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="salario_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.funcionario} {self.valor} ({self.desde:%d/%m/%Y})"


class Folha(ModeloDaClinica):
    """An employee's pay for one month: salary, overtime and absences.

    Once launched it becomes a payable (`lancamento`) and is no longer edited here; to
    redo it, cancel the payable in finance first.
    """

    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.PROTECT, related_name="folhas", verbose_name=_("funcionário")
    )
    competencia = models.DateField(_("competência"), help_text=_("O primeiro dia do mês."))
    salario = models.DecimalField(_("salário"), **DINHEIRO)
    horas_extras = models.DecimalField(
        _("horas extras"), max_digits=6, decimal_places=2, default=Decimal(0)
    )
    valor_hora_extra = models.DecimalField(_("valor da hora extra"), **DINHEIRO, default=Decimal(0))
    faltas = models.PositiveSmallIntegerField(_("dias de falta"), default=0)
    observacao = models.CharField(_("observação"), max_length=200, blank=True)
    lancamento = models.OneToOneField(
        "financeiro.Lancamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha",
        verbose_name=_("conta a pagar"),
    )

    class Meta:
        verbose_name = _("folha do mês")
        verbose_name_plural = _("folhas do mês")
        ordering = ["-competencia", "funcionario__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "funcionario", "competencia"], name="folha_unica_por_mes"
            ),
            models.CheckConstraint(condition=Q(competencia__day=1), name="folha_competencia_dia_1"),
        ]

    def __str__(self):
        return f"{self.funcionario} {self.competencia:%m/%Y}"

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        if self.clinica_id is None:  # without isolation (commands)
            self.clinica_id = self.funcionario.clinica_id
        if self.funcionario.clinica_id != self.clinica_id:
            raise ClinicaDiferente("The employee must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def valor_horas_extras(self):
        return (self.horas_extras * self.valor_hora_extra).quantize(CENTAVO, ROUND_HALF_UP)

    @property
    def desconto_faltas(self):
        return (self.salario / DIAS_POR_MES * self.faltas).quantize(CENTAVO, ROUND_HALF_UP)

    @property
    def total(self):
        return self.salario + self.valor_horas_extras - self.desconto_faltas

    @property
    def lancada(self):
        return self.lancamento_id is not None and not self.lancamento.cancelado


def hora_extra_sugerida(salario):
    """Overtime hour from a monthly salary: salary / 220 hours x 1.5 (CLT minimum)."""
    return (salario / HORAS_POR_MES * ADICIONAL_HORA_EXTRA).quantize(CENTAVO, ROUND_HALF_UP)
