from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import CampoDecimal, FormularioBootstrap
from apps.core.validadores import cpf_valido, normalizar_telefone, somente_digitos
from apps.financeiro.models import Categoria

from .models import Folha, Funcionario

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

    cpf = forms.CharField(label=_("CPF"), max_length=14, required=False)
    telefone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )
    salario = _dinheiro(_("Salário"), obrigatorio=False)
    salario_desde = forms.DateField(label=_("Salário a partir de"), widget=DATA, required=False)

    class Meta:
        model = Funcionario
        fields = [
            "nome",
            "cpf",
            "cargo",
            "admissao",
            "desligamento",
            "telefone",
            "observacoes",
            "ativo",
        ]
        widgets = {
            "admissao": DATA,
            "desligamento": DATA,
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["salario"].label = _("Novo salário")
            self.fields["salario"].help_text = _(
                "Só para um aumento ou mudança: o anterior fica no histórico."
            )
        else:
            self.fields["salario"].required = True
            self.fields["salario_desde"].help_text = _("Em branco: a data de admissão ou hoje.")

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data.get("cpf"))
        if cpf and not cpf_valido(cpf):
            raise forms.ValidationError(_("CPF inválido."))
        if cpf and Funcionario.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um funcionário com este CPF."))
        return cpf

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get("telefone"))

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
        model = Folha
        fields = ["horas_extras", "valor_hora_extra", "faltas", "observacao"]

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
    categoria = forms.ModelChoiceField(label=_("Categoria"), queryset=Categoria.objects.none())
    vencimento = forms.DateField(label=_("Vencimento"), widget=DATA)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        despesas = Categoria.objects.filter(tipo=Categoria.Tipo.DESPESA, ativa=True)
        self.fields["categoria"].queryset = despesas
        self.fields["categoria"].initial = despesas.filter(nome="Salários e encargos").first()
