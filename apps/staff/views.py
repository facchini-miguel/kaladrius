"""Staff and the month's pay (decision 099): administrators and Finance only."""

import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.core.permissions import Action, Module, can, requires_permission

from . import services
from .forms import EmployeeForm, PayrollForm, PostPayrollForm
from .models import Employee, Payroll, Salary


@requires_permission(Module.STAFF, Action.VIEW)
def employee_list(request):
    employees = list(Employee.objects.all())
    today = timezone.localdate()
    for employee in employees:
        employee.current_salary = employee.salary_on(today)
    return render(request, "staff/list.html", {"employees": employees})


@requires_permission(Module.STAFF, Action.VIEW)
def employee(request, pk):
    employee = get_object_or_404(Employee.objects, pk=pk)
    return render(
        request,
        "staff/employee.html",
        {
            "employee": employee,
            "salaries": employee.salaries.select_related("created_by"),
            "payslips": employee.payrolls.select_related("entry")[:24],
            "current_salary": employee.salary_on(timezone.localdate()),
        },
    )


@requires_permission(Module.STAFF, Action.CREATE)
def new_employee(request):
    return _employee_form(request, Employee())


@requires_permission(Module.STAFF, Action.CHANGE)
def edit_employee(request, pk):
    return _employee_form(request, get_object_or_404(Employee.objects, pk=pk))


def _employee_form(request, instance):
    form = EmployeeForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            employee = form.save()
            if form.cleaned_data.get("salary"):
                Salary.objects.create(
                    employee=employee,
                    amount=form.cleaned_data["salary"],
                    effective_from=form.cleaned_data["salary_since"],
                    created_by=request.user,
                )
        messages.success(request, _("%(nome)s saved.") % {"nome": employee.name})
        return redirect("staff:employee", pk=employee.pk)
    return render(request, "staff/form.html", {"form": form, "instance": instance})


@requires_permission(Module.STAFF, Action.VIEW)
def payroll(request):
    """The month's pay: one line per employee; save it, then launch it into finance."""
    today = timezone.localdate()
    period = services.month_from_url(request.GET.get("month"), today)
    url = f"{reverse('staff:payroll')}?month={period:%Y-%m}"
    can_change = can(request, Module.STAFF, Action.CHANGE)
    payrolls = (
        services.prepare(period)
        if can_change
        else list(Payroll.objects.filter(period=period).select_related("employee", "entry"))
    )
    data = request.POST if request.method == "POST" else None
    rows = [
        (
            f,
            None
            if f.is_posted or not can_change
            # By employee: a sheet not saved yet has no pk.
            else PayrollForm(data, instance=f, prefix=f"f{f.employee_id}"),
        )
        for f in payrolls
    ]
    post_form = PostPayrollForm(
        data if data and data.get("action") == "lancar" else None,
        initial={"due_date": services.end_of_month(period) + datetime.timedelta(days=5)},
    )
    if request.method == "POST":
        if not can_change:
            return redirect(url)
        form_list = [form for _payroll, form in rows if form is not None]
        if all(form.is_valid() for form in form_list):
            with transaction.atomic():
                for form in form_list:
                    form.save()
            if request.POST.get("action") != "lancar":
                messages.success(request, _("Pay saved."))
                return redirect(url)
            if post_form.is_valid():
                try:
                    posted = services.post_payroll(
                        [f for f, form in rows if form is not None],
                        category=post_form.cleaned_data["category"],
                        due_date=post_form.cleaned_data["due_date"],
                        user=request.user,
                    )
                except ValidationError as error:
                    messages.error(request, error.messages[0])
                else:
                    messages.success(
                        request,
                        ngettext(
                            "%(n)s payable created in finance.",
                            "%(n)s payables created in finance.",
                            posted,
                        )
                        % {"n": posted},
                    )
                    return redirect(url)
    previous = (period - datetime.timedelta(days=1)).replace(day=1)
    following = services.end_of_month(period) + datetime.timedelta(days=1)
    return render(
        request,
        "staff/payroll.html",
        {
            "period": period,
            "rows": rows,
            "post_form": post_form,
            "can_change": can_change,
            "pending": any(form is not None for _payroll, form in rows),
            "total": sum((f.total for f in payrolls), start=0),
            "previous": previous,
            "following": following,
        },
    )
