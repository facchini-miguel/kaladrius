"""The month's pay (decision 099): prepared per employee, then launched as payables."""

import calendar
import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.ordering import chave_alfabetica
from apps.finance import services as financeiro
from apps.finance.models import Entry

from .models import Employee, Payroll, hora_extra_sugerida


def competencia_de(date):
    return date.replace(day=1)


def fim_do_mes(competencia):
    return competencia.replace(day=calendar.monthrange(competencia.year, competencia.month)[1])


def preparar(competencia):
    """The month's sheets: one per employee working in the month that has a salary.

    Sheets already saved keep what was typed; the missing ones come unsaved, with the
    salary in force at the end of the month and the suggested overtime hour. Only saving
    the page stores them, so looking at a month (even a future one) leaves nothing behind.
    """
    end = fim_do_mes(competencia)
    trabalhando = (
        Employee.objects.filter(active=True)
        .exclude(admissao__gt=end)
        .exclude(desligamento__lt=competencia)
    )
    folhas = list(
        Payroll.objects.filter(competencia=competencia).select_related("employee", "entry")
    )
    existentes = {f.employee_id for f in folhas}
    for employee in trabalhando:
        salario = employee.salario_em(end)
        if employee.pk in existentes or salario is None:
            continue
        folhas.append(
            Payroll(
                employee=employee,
                competencia=competencia,
                salario=salario,
                valor_hora_extra=hora_extra_sugerida(salario),
            )
        )
    return sorted(folhas, key=lambda f: chave_alfabetica(f.employee.name))


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
        mes = f"{folha.competencia:%m/%Y}"
        folha.entry = financeiro.criar_lancamento(
            clinic=folha.employee.clinic,
            kind=Entry.Tipo.PAGAR,
            payer=folha.employee.name,
            description=_("Salário %(mes)s") % {"mes": mes},
            category=category,
            notes=_("Salário %(salario)s + horas extras %(extras)s − faltas %(faltas)s.")
            % {
                "salario": folha.salario,
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


def mes_da_url(texto, hoje):
    """The month asked as YYYY-MM, or the current one."""
    try:
        return datetime.datetime.strptime(texto or "", "%Y-%m").date()
    except ValueError:
        return competencia_de(hoje)
