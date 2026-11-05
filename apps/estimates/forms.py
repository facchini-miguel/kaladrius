from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapForm
from apps.dentistry.teeth import DENTES_VALIDOS
from apps.finance.forms import DATE_INPUT, _methods_with_blank, _money_field
from apps.finance.models import Category, FinancialAccount
from apps.health_plans import insurance
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from .models import Estimate, EstimateItem, Procedure


class ProcedureForm(BootstrapForm, forms.ModelForm):
    amount = _money_field(_("Valor"))

    class Meta:
        model = Procedure
        fields = ["name", "code", "amount", "category", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Kind.INCOME, active=True
        )
        # The country's procedure coding (decision 125): TUSS, CDT, ADA item number...
        self.codificacao = insurance.for_country().procedure
        self.fields["code"].label = insurance.code_label()
        if self.codificacao and self.codificacao.example:
            self.fields["code"].widget.attrs["placeholder"] = self.codificacao.example
        self.fields["code"].help_text = _("Opcional. Vai para os orçamentos.")

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if self.codificacao:
            return self.codificacao.clean_value(code)
        return code

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Procedure.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um procedimento com este nome."))
        return name


class EstimateForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ["patient", "practitioner", "date", "valid_until", "notes"]
        widgets = {
            "patient": forms.HiddenInput,
            "date": DATE_INPUT,
            "valid_until": DATE_INPUT,
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = Patient.objects.filter(archived=False)
        self.fields["patient"].error_messages["required"] = _("Escolha o paciente.")
        self.fields["practitioner"].queryset = Practitioner.objects.filter(active=True)

    def clean(self):
        data = super().clean()
        if data.get("date") and data.get("valid_until") and data["valid_until"] < data["date"]:
            self.add_error("valid_until", _("A validade não pode ser antes da data do orçamento."))
        return data


class EstimateItemForm(BootstrapForm, forms.ModelForm):
    """One line of the estimate; price and description come from the procedure if empty."""

    unit_price = _money_field(_("Valor unitário"), obrigatorio=False)

    class Meta:
        model = EstimateItem
        fields = ["procedure", "description", "teeth", "faces", "quantity", "unit_price"]
        widgets = {"teeth": forms.HiddenInput}

    def __init__(self, *args, dentistry=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.dentistry = dentistry
        self.fields["procedure"].queryset = Procedure.objects.filter(active=True)
        self.fields["description"].required = False
        if not dentistry:
            # Teeth and faces belong to the dental module (decision 080).
            del self.fields["teeth"], self.fields["faces"]

    def clean_teeth(self):
        partes = [p.strip() for p in (self.cleaned_data.get("teeth") or "").split(",")]
        teeth = sorted({int(p) for p in partes if p.isdecimal()})
        if any(d not in DENTES_VALIDOS for d in teeth):
            raise forms.ValidationError(_("Dente inválido."))
        return ",".join(str(d) for d in teeth)

    def clean(self):
        data = super().clean()
        procedure = data.get("procedure")
        if not self.dentistry and any(
            self.data.get(self.add_prefix(field), "").strip() for field in ("teeth", "faces")
        ):
            raise forms.ValidationError(_("Habilite Odontologia para registrar dentes ou faces."))
        # The procedure's code is copied, like its description and price.
        self.instance.code = procedure.code if procedure else ""
        if not (data.get("description") or "").strip():
            if procedure is None:
                self.add_error("description", _("Escolha um procedimento ou descreva o item."))
            else:
                data["description"] = procedure.name
        if data.get("unit_price") is None:
            if procedure is None:
                self.add_error("unit_price", _("Informe o valor."))
            else:
                data["unit_price"] = procedure.amount
        return data


class DiscountForm(BootstrapForm, forms.Form):
    discount = _money_field(_("Desconto no total"), obrigatorio=False)


class ApproveEstimateForm(BootstrapForm, forms.Form):
    parcelas = forms.IntegerField(
        label=_("Número de parcelas"), min_value=1, max_value=48, initial=1
    )
    primeiro_vencimento = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATE_INPUT, initial=timezone.localdate
    )
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    recebido_agora = forms.BooleanField(label=_("A 1ª parcela já foi paga agora"), required=False)
    method = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_methods_with_blank,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Kind.INCOME, active=True
        )
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)

    def clean(self):
        data = super().clean()
        if data.get("recebido_agora"):
            for field in ("method", "account"):
                if not data.get(field):
                    self.add_error(field, _("Informe para registrar o pagamento."))
        return data
