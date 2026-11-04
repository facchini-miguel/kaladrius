"""Staff, salaries and the month's pay (decision 099, legacy Medical planocontas).

The clinic keeps the record and turns each month's pay into a payable. Payroll taxes and
benefits (INSS, FGTS, 13th salary, vacations) stay with the accountant.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicaDiferente, ModeloDaClinica
from apps.core.ordering import ALFABETICA

DINHEIRO = {"max_digits": 12, "decimal_places": 2}
CENTAVO = Decimal("0.01")
# Monthly hours of a 44-hour week (CLT) and the minimum overtime rate (+50%).
HORAS_POR_MES = Decimal(220)
ADICIONAL_HORA_EXTRA = Decimal("1.5")
DIAS_POR_MES = Decimal(30)


class Employee(ModeloDaClinica):
    name = models.CharField(_("nome"), max_length=200, db_collation=ALFABETICA, db_column="nome")
    # The country's employee document (decision 121); the name stayed from Brazil.
    cpf = models.CharField(_("documento"), max_length=20, blank=True)
    cargo = models.CharField(_("cargo"), max_length=100, blank=True)
    admissao = models.DateField(_("admissão"), null=True, blank=True)
    desligamento = models.DateField(_("desligamento"), null=True, blank=True)
    phone = models.CharField(_("telefone"), max_length=11, blank=True, db_column="telefone")
    notes = models.TextField(_("observações"), blank=True, db_column="observacoes")
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "pessoal_funcionario"
        verbose_name = _("funcionário")
        verbose_name_plural = _("funcionários")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "cpf"],
                condition=~Q(cpf=""),
                name="funcionario_cpf_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.name

    papel_documento = "funcionario"  # see apps/core/identification.py

    def salario_em(self, date):
        """The salary in force on `data` (the newest one starting on or before it)."""
        salario = self.salarios.filter(desde__lte=date).order_by("-desde", "-pk").first()
        return salario.amount if salario else None


class Salary(ModeloDaClinica):
    """One salary change: the history the legacy kept in salario_fixo_hist."""

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salarios",
        verbose_name=_("funcionário"),
        db_column="funcionario_id",
    )
    amount = models.DecimalField(_("salário"), **DINHEIRO, db_column="valor")
    desde = models.DateField(_("desde"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "pessoal_salario"
        verbose_name = _("salário")
        verbose_name_plural = _("salários")
        ordering = ["-desde", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="salario_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.employee} {self.amount} ({self.desde:%d/%m/%Y})"


class Payroll(ModeloDaClinica):
    """An employee's pay for one month: salary, overtime and absences.

    Once launched it becomes a payable (`lancamento`) and is no longer edited here; to
    redo it, cancel the payable in finance first.
    """

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="folhas",
        verbose_name=_("funcionário"),
        db_column="funcionario_id",
    )
    competencia = models.DateField(_("competência"), help_text=_("O primeiro dia do mês."))
    salario = models.DecimalField(_("salário"), **DINHEIRO)
    horas_extras = models.DecimalField(
        _("horas extras"), max_digits=6, decimal_places=2, default=Decimal(0)
    )
    valor_hora_extra = models.DecimalField(_("valor da hora extra"), **DINHEIRO, default=Decimal(0))
    faltas = models.PositiveSmallIntegerField(_("dias de falta"), default=0)
    note = models.CharField(_("observação"), max_length=200, blank=True, db_column="observacao")
    entry = models.OneToOneField(
        "financeiro.Entry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folha",
        verbose_name=_("conta a pagar"),
        db_column="lancamento_id",
    )

    class Meta:
        db_table = "pessoal_folha"
        verbose_name = _("folha do mês")
        verbose_name_plural = _("folhas do mês")
        ordering = ["-competencia", "employee__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "employee", "competencia"], name="folha_unica_por_mes"
            ),
            models.CheckConstraint(condition=Q(competencia__day=1), name="folha_competencia_dia_1"),
        ]

    def __str__(self):
        return f"{self.employee} {self.competencia:%m/%Y}"

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.employee.clinic_id
        if self.employee.clinic_id != self.clinic_id:
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
        return self.entry_id is not None and not self.entry.cancelado


def hora_extra_sugerida(salario):
    """Overtime hour from a monthly salary: salary / 220 hours x 1.5 (CLT minimum)."""
    return (salario / HORAS_POR_MES * ADICIONAL_HORA_EXTRA).quantize(CENTAVO, ROUND_HALF_UP)
