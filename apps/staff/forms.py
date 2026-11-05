from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import identification
from apps.core.forms import CampoDecimal, FormularioBootstrap, campo_documento
from apps.core.validators import normalizar_telefone
from apps.finance.models import Category

from .models import Employee, Payroll

DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _dinheiro(label, obrigatorio):
    return CampoDecimal(
        label=label,
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=obrigatorio,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )


class FuncionarioForm(FormularioBootstrap, forms.ModelForm):
    """The employee and, on registering or on a raise, the salary from a date."""

    tax_id = campo_documento()  # the country's employee document (decision 121)
    phone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )
    salary = _dinheiro(_("Salário"), obrigatorio=False)
    salario_desde = forms.DateField(label=_("Salário a partir de"), widget=DATA, required=False)

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
            "hired_on": DATA,
            "left_on": DATA,
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # None in Australia: the law restricts who may record the tax file number.
        self.document = identification.do_pais().funcionario
        if self.document is None:
            del self.fields["tax_id"]
        else:
            self.fields["tax_id"].label = self.document.sigla
            self.fields["tax_id"].widget.attrs["placeholder"] = self.document.example
        if self.instance.pk:
            self.fields["salary"].label = _("Novo salário")
            self.fields["salary"].help_text = _(
                "Só para um aumento ou mudança: o anterior fica no histórico."
            )
        else:
            self.fields["salary"].required = True
            self.fields["salario_desde"].help_text = _("Em branco: a data de admissão ou hoje.")

    def clean_tax_id(self):
        tax_id = identification.limpar(
            self.cleaned_data.get("tax_id"), [self.document], self.document.sigla
        )
        if tax_id and Employee.objects.filter(tax_id=tax_id).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um funcionário com este documento."))
        return tax_id

    def clean_phone(self):
        return normalizar_telefone(self.cleaned_data.get("phone"))

    def clean(self):
        data = super().clean()
        salary = data.get("salary")
        if salary is not None and salary <= 0:
            self.add_error("salary", _("Informe um valor maior que zero."))
        if salary and not data.get("salario_desde"):
            if self.instance.pk:
                self.add_error(
                    "salario_desde", _("Informe a partir de quando vale o novo salário.")
                )
            else:
                data["salario_desde"] = data.get("hired_on") or timezone.localdate()
        hired_on, left_on = data.get("hired_on"), data.get("left_on")
        if hired_on and left_on and left_on < hired_on:
            self.add_error("left_on", _("O desligamento não pode ser antes da admissão."))
        return data


class FolhaForm(FormularioBootstrap, forms.ModelForm):
    """One employee's line of the month: overtime, absences and a note."""

    overtime_hours = CampoDecimal(
        label=_("Horas extras"), max_digits=6, decimal_places=2, min_value=0, localize=True
    )
    overtime_rate = _dinheiro(_("Valor da hora extra"), obrigatorio=True)

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
            raise forms.ValidationError(_("No máximo 30 dias de falta."))
        return absences


class LancarForm(FormularioBootstrap, forms.Form):
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    due_date = forms.DateField(label=_("Vencimento"), widget=DATA)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        despesas = Category.objects.filter(kind=Category.Tipo.DESPESA, active=True)
        self.fields["category"].queryset = despesas
        self.fields["category"].initial = despesas.filter(name="Salários e encargos").first()
