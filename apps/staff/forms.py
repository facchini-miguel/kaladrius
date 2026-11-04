from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import identification
from apps.core.forms import CampoDecimal, FormularioBootstrap, campo_documento
from apps.core.validators import normalizar_telefone
from apps.finance.models import Category

from .models import Employee, Payroll

DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _dinheiro(rotulo, obrigatorio):
    return CampoDecimal(
        label=rotulo,
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=obrigatorio,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )


class FuncionarioForm(FormularioBootstrap, forms.ModelForm):
    """The employee and, on registering or on a raise, the salary from a date."""

    cpf = campo_documento()  # the country's employee document (decision 121)
    phone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )
    salario = _dinheiro(_("Salário"), obrigatorio=False)
    salario_desde = forms.DateField(label=_("Salário a partir de"), widget=DATA, required=False)

    class Meta:
        model = Employee
        fields = [
            "name",
            "cpf",
            "cargo",
            "admissao",
            "desligamento",
            "phone",
            "notes",
            "active",
        ]
        widgets = {
            "admissao": DATA,
            "desligamento": DATA,
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # None in Australia: the law restricts who may record the tax file number.
        self.document = identification.do_pais().funcionario
        if self.document is None:
            del self.fields["cpf"]
        else:
            self.fields["cpf"].label = self.document.sigla
            self.fields["cpf"].widget.attrs["placeholder"] = self.document.exemplo
        if self.instance.pk:
            self.fields["salario"].label = _("Novo salário")
            self.fields["salario"].help_text = _(
                "Só para um aumento ou mudança: o anterior fica no histórico."
            )
        else:
            self.fields["salario"].required = True
            self.fields["salario_desde"].help_text = _("Em branco: a data de admissão ou hoje.")

    def clean_cpf(self):
        cpf = identification.limpar(
            self.cleaned_data.get("cpf"), [self.document], self.document.sigla
        )
        if cpf and Employee.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um funcionário com este documento."))
        return cpf

    def clean_phone(self):
        return normalizar_telefone(self.cleaned_data.get("phone"))

    def clean(self):
        dados = super().clean()
        salario = dados.get("salario")
        if salario is not None and salario <= 0:
            self.add_error("salario", _("Informe um valor maior que zero."))
        if salario and not dados.get("salario_desde"):
            if self.instance.pk:
                self.add_error(
                    "salario_desde", _("Informe a partir de quando vale o novo salário.")
                )
            else:
                dados["salario_desde"] = dados.get("admissao") or timezone.localdate()
        admissao, desligamento = dados.get("admissao"), dados.get("desligamento")
        if admissao and desligamento and desligamento < admissao:
            self.add_error("desligamento", _("O desligamento não pode ser antes da admissão."))
        return dados


class FolhaForm(FormularioBootstrap, forms.ModelForm):
    """One employee's line of the month: overtime, absences and a note."""

    horas_extras = CampoDecimal(
        label=_("Horas extras"), max_digits=6, decimal_places=2, min_value=0, localize=True
    )
    valor_hora_extra = _dinheiro(_("Valor da hora extra"), obrigatorio=True)

    class Meta:
        model = Payroll
        fields = ["horas_extras", "valor_hora_extra", "faltas", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] += " form-control-sm"
        self.fields["faltas"].widget.attrs["max"] = 31

    def clean_faltas(self):
        faltas = self.cleaned_data["faltas"]
        if faltas > 30:
            raise forms.ValidationError(_("No máximo 30 dias de falta."))
        return faltas


class LancarForm(FormularioBootstrap, forms.Form):
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    due_date = forms.DateField(label=_("Vencimento"), widget=DATA)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        despesas = Category.objects.filter(kind=Category.Tipo.DESPESA, active=True)
        self.fields["category"].queryset = despesas
        self.fields["category"].initial = despesas.filter(name="Salários e encargos").first()
