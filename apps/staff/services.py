"""The month's pay (decision 099): prepared per employee, then launched as payables."""

import calendar
import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.ordering import alphabetical_key
from apps.finance import services as finance_services
from apps.finance.models import Entry

from .models import Employee, Payroll, suggested_overtime_rate


def period_of(date):
    return date.replace(day=1)


def end_of_month(period):
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])


def prepare(period):
    """The month's sheets: one per employee working in the month that has a salary.

    Sheets already saved keep what was typed; the missing ones come unsaved, with the
    salary in force at the end of the month and the suggested overtime hour. Only saving
    the page stores them, so looking at a month (even a future one) leaves nothing behind.
    """
    end = end_of_month(period)
    working = (
        Employee.objects.filter(active=True).exclude(hired_on__gt=end).exclude(left_on__lt=period)
    )
    payrolls = list(Payroll.objects.filter(period=period).select_related("employee", "entry"))
    existing = {f.employee_id for f in payrolls}
    for employee in working:
        salary = employee.salary_on(end)
        if employee.pk in existing or salary is None:
            continue
        payrolls.append(
            Payroll(
                employee=employee,
                period=period,
                salary=salary,
                overtime_rate=suggested_overtime_rate(salary),
            )
        )
    return sorted(payrolls, key=lambda f: alphabetical_key(f.employee.name))


@transaction.atomic
def post_payroll(payrolls, *, category, due_date, user):
    """Turn the sheets not yet launched into payables, one per employee."""
    posted = 0
    for payroll in payrolls:
        payroll = Payroll.objects.select_for_update().select_related("employee").get(pk=payroll.pk)
        if payroll.is_posted:
            continue
        if payroll.total <= 0:
            raise ValidationError(
                _("O total de %(nome)s precisa ser maior que zero.") % {"nome": payroll.employee}
            )
        month = f"{payroll.period:%m/%Y}"
        payroll.entry = finance_services.create_entry(
            clinic=payroll.employee.clinic,
            kind=Entry.Kind.PAYABLE,
            payer=payroll.employee.name,
            description=_("Salário %(mes)s") % {"mes": month},
            category=category,
            notes=_("Salário %(salario)s + horas extras %(extras)s − faltas %(faltas)s.")
            % {
                "salario": payroll.salary,
                "extras": payroll.overtime_amount,
                "faltas": payroll.absence_deduction,
            },
            total_amount=payroll.total,
            installments=1,
            first_due_date=due_date,
            user=user,
        )
        payroll.save(update_fields=["entry"])
        posted += 1
    return posted


def month_from_url(text, today):
    """The month asked as YYYY-MM, or the current one."""
    try:
        return datetime.datetime.strptime(text or "", "%Y-%m").date()
    except ValueError:
        return period_of(today)
