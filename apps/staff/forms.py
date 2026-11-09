from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import identification
from apps.core.forms import BootstrapForm, LocalizedDecimalField, document_field
from apps.core.validators import normalize_phone
from apps.finance.models import PAYROLL, Category

from .models import Employee, Payroll

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _money(label, required):
    return LocalizedDecimalField(
        label=label,
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=required,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )


class EmployeeForm(BootstrapForm, forms.ModelForm):
    """The employee and, on registering or on a raise, the salary from a date."""

    tax_id = document_field()  # the country's employee document (decision 121)
    phone = forms.CharField(
        label=_("Phone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )
    salary = _money(_("Salary"), required=False)
    salary_since = forms.DateField(label=_("Salary from"), widget=DATE_INPUT, required=False)

    class Meta:
        model = Employee
        fields = [
            "name",
            "tax_id",
            "job_title",
            "hired_on",
            "left_on",
            "phone",
            "notes",
            "active",
        ]
        widgets = {
            "hired_on": DATE_INPUT,
            "left_on": DATE_INPUT,
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # None in Australia: the law restricts who may record the tax file number.
        self.document = identification.for_country().employee
        if self.document is None:
            del self.fields["tax_id"]
        else:
            self.fields["tax_id"].label = self.document.abbreviation
            self.fields["tax_id"].widget.attrs["placeholder"] = self.document.example
        if self.instance.pk:
            self.fields["salary"].label = _("New salary")
            self.fields["salary"].help_text = _(
                "Only for a raise or change: the previous one stays in the history."
            )
        else:
            self.fields["salary"].required = True
            self.fields["salary_since"].help_text = _("Blank: the hiring date, or today.")

    def clean_tax_id(self):
        tax_id = identification.clean_value(
            self.cleaned_data.get("tax_id"), [self.document], self.document.abbreviation
        )
        if tax_id and Employee.objects.filter(tax_id=tax_id).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("An employee with this document already exists."))
        return tax_id

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))

    def clean(self):
        data = super().clean()
        salary = data.get("salary")
        if salary is not None and salary <= 0:
            self.add_error("salary", _("Enter an amount greater than zero."))
        if salary and not data.get("salary_since"):
            if self.instance.pk:
                self.add_error("salary_since", _("Enter from when the new salary applies."))
            else:
                data["salary_since"] = data.get("hired_on") or timezone.localdate()
        hired_on, left_on = data.get("hired_on"), data.get("left_on")
        if hired_on and left_on and left_on < hired_on:
            self.add_error("left_on", _("The leaving date cannot be before the hiring date."))
        return data


class PayrollForm(BootstrapForm, forms.ModelForm):
    """One employee's line of the month: overtime, absences and a note."""

    overtime_hours = LocalizedDecimalField(
        label=_("Overtime"), max_digits=6, decimal_places=2, min_value=0, localize=True
    )
    overtime_rate = _money(_("Overtime hourly rate"), required=True)

    class Meta:
        model = Payroll
        fields = ["overtime_hours", "overtime_rate", "absences", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] += " form-control-sm"
        self.fields["absences"].widget.attrs["max"] = 31

    def clean_absences(self):
        absences = self.cleaned_data["absences"]
        if absences > 30:
            raise forms.ValidationError(_("At most 30 days of absence."))
        return absences


class PostPayrollForm(BootstrapForm, forms.Form):
    category = forms.ModelChoiceField(label=_("Category"), queryset=Category.objects.none())
    due_date = forms.DateField(label=_("Due date"), widget=DATE_INPUT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expenses = Category.objects.filter(kind=Category.Kind.EXPENSE, active=True)
        self.fields["category"].queryset = expenses
        self.fields["category"].initial = expenses.filter(key=PAYROLL).first()
