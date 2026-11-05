"""Staff, salaries and the month's pay (decision 099, legacy Medical planocontas).

The clinic keeps the record and turns each month's pay into a payable. Payroll taxes and
benefits (INSS, FGTS, 13th salary, vacations) stay with the accountant.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel, WrongClinic
from apps.core.ordering import ALPHABETICAL

MONEY = {"max_digits": 12, "decimal_places": 2}
CENT = Decimal("0.01")
# Monthly hours of a 44-hour week (CLT) and the minimum overtime rate (+50%).
HOURS_PER_MONTH = Decimal(220)
OVERTIME_PREMIUM = Decimal("1.5")
DAYS_PER_MONTH = Decimal(30)


class Employee(ClinicModel):
    name = models.CharField(_("nome"), max_length=200, db_collation=ALPHABETICAL, db_column="nome")
    # The country's employee document (decision 121); the name stayed from Brazil.
    tax_id = models.CharField(_("documento"), max_length=20, blank=True, db_column="cpf")
    job_title = models.CharField(_("cargo"), max_length=100, blank=True, db_column="cargo")
    hired_on = models.DateField(_("admissão"), null=True, blank=True, db_column="admissao")
    left_on = models.DateField(_("desligamento"), null=True, blank=True, db_column="desligamento")
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
                fields=["clinic", "tax_id"],
                condition=~Q(tax_id=""),
                name="funcionario_cpf_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.name

    document_role = "funcionario"  # see apps/core/identification.py

    def salary_on(self, date):
        """The salary in force on `data` (the newest one starting on or before it)."""
        salary = (
            self.salarios.filter(effective_from__lte=date)
            .order_by("-effective_from", "-pk")
            .first()
        )
        return salary.amount if salary else None


class Salary(ClinicModel):
    """One salary change: the history the legacy kept in salario_fixo_hist."""

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salarios",
        verbose_name=_("funcionário"),
        db_column="funcionario_id",
    )
    amount = models.DecimalField(_("salário"), **MONEY, db_column="valor")
    effective_from = models.DateField(_("desde"), db_column="desde")
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
        ordering = ["-effective_from", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="salario_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.employee} {self.amount} ({self.effective_from:%d/%m/%Y})"


class Payroll(ClinicModel):
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
    period = models.DateField(
        _("competência"), help_text=_("O primeiro dia do mês."), db_column="competencia"
    )
    salary = models.DecimalField(_("salário"), **MONEY, db_column="salario")
    overtime_hours = models.DecimalField(
        _("horas extras"),
        max_digits=6,
        decimal_places=2,
        default=Decimal(0),
        db_column="horas_extras",
    )
    overtime_rate = models.DecimalField(
        _("valor da hora extra"), **MONEY, default=Decimal(0), db_column="valor_hora_extra"
    )
    absences = models.PositiveSmallIntegerField(_("dias de falta"), default=0, db_column="faltas")
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
        ordering = ["-period", "employee__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "employee", "period"], name="folha_unica_por_mes"
            ),
            models.CheckConstraint(condition=Q(period__day=1), name="folha_competencia_dia_1"),
        ]

    def __str__(self):
        return f"{self.employee} {self.period:%m/%Y}"

    def save(self, *args, **kwargs):
        self._check_clinic()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.employee.clinic_id
        if self.employee.clinic_id != self.clinic_id:
            raise WrongClinic("The employee must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def overtime_amount(self):
        return (self.overtime_hours * self.overtime_rate).quantize(CENT, ROUND_HALF_UP)

    @property
    def absence_deduction(self):
        return (self.salary / DAYS_PER_MONTH * self.absences).quantize(CENT, ROUND_HALF_UP)

    @property
    def total(self):
        return self.salary + self.overtime_amount - self.absence_deduction

    @property
    def is_posted(self):
        return self.entry_id is not None and not self.entry.cancelled


def suggested_overtime_rate(salary):
    """Overtime hour from a monthly salary: salary / 220 hours x 1.5 (CLT minimum)."""
    return (salary / HOURS_PER_MONTH * OVERTIME_PREMIUM).quantize(CENT, ROUND_HALF_UP)
