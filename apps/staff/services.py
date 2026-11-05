"""The month's pay (decision 099): prepared per employee, then launched as payables."""

import calendar
import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.ordering import alphabetical_key
from apps.finance import services as financeiro
from apps.finance.models import Entry

from .models import Employee, Payroll, hora_extra_sugerida


def competencia_de(date):
    return date.replace(day=1)


def fim_do_mes(period):
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])


def preparar(period):
    """The month's sheets: one per employee working in the month that has a salary.

    Sheets already saved keep what was typed; the missing ones come unsaved, with the
    salary in force at the end of the month and the suggested overtime hour. Only saving
    the page stores them, so looking at a month (even a future one) leaves nothing behind.
    """
    end = fim_do_mes(period)
    trabalhando = (
        Employee.objects.filter(active=True).exclude(hired_on__gt=end).exclude(left_on__lt=period)
    )
    folhas = list(Payroll.objects.filter(period=period).select_related("employee", "entry"))
    existentes = {f.employee_id for f in folhas}
    for employee in trabalhando:
        salary = employee.salario_em(end)
        if employee.pk in existentes or salary is None:
            continue
        folhas.append(
            Payroll(
                employee=employee,
                period=period,
                salary=salary,
                overtime_rate=hora_extra_sugerida(salary),
            )
        )
    return sorted(folhas, key=lambda f: alphabetical_key(f.employee.name))


@transaction.atomic
def lancar(folhas, *, category, due_date, user):
    """Turn the sheets not yet launched into payables, one per employee."""
    lancadas = 0
    for folha in folhas:
        folha = Payroll.objects.select_for_update().select_related("employee").get(pk=folha.pk)
        if folha.lancada:
            continue
        if folha.total <= 0:
            raise ValidationError(
                _("O total de %(nome)s precisa ser maior que zero.") % {"nome": folha.employee}
            )
        month = f"{folha.period:%m/%Y}"
        folha.entry = financeiro.criar_lancamento(
            clinic=folha.employee.clinic,
            kind=Entry.Tipo.PAGAR,
            payer=folha.employee.name,
            description=_("Salário %(mes)s") % {"mes": month},
            category=category,
            notes=_("Salário %(salario)s + horas extras %(extras)s − faltas %(faltas)s.")
            % {
                "salario": folha.salary,
                "extras": folha.valor_horas_extras,
                "faltas": folha.desconto_faltas,
            },
            total_amount=folha.total,
            parcelas=1,
            primeiro_vencimento=due_date,
            user=user,
        )
        folha.save(update_fields=["entry"])
        lancadas += 1
    return lancadas


def mes_da_url(text, today):
    """The month asked as YYYY-MM, or the current one."""
    try:
        return datetime.datetime.strptime(text or "", "%Y-%m").date()
    except ValueError:
        return competencia_de(today)
