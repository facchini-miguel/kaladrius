from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.dentistry.teeth import DENTES_VALIDOS
from apps.finance.forms import DATA, _campo_dinheiro, _formas_com_vazio
from apps.finance.models import Category, FinancialAccount
from apps.health_plans import insurance
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from .models import Estimate, EstimateItem, Procedure


class ProcedimentoForm(FormularioBootstrap, forms.ModelForm):
    amount = _campo_dinheiro(_("Valor"))

    class Meta:
        model = Procedure
        fields = ["name", "code", "amount", "categoria", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Category.objects.filter(
            kind=Category.Tipo.RECEITA, active=True
        )
        # The country's procedure coding (decision 125): TUSS, CDT, ADA item number...
        self.codificacao = insurance.do_pais().procedimento
        self.fields["code"].label = insurance.rotulo_do_codigo()
        if self.codificacao and self.codificacao.exemplo:
            self.fields["code"].widget.attrs["placeholder"] = self.codificacao.exemplo
        self.fields["code"].help_text = _("Opcional. Vai para os orçamentos.")

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if self.codificacao:
            return self.codificacao.limpar(code)
        return code

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Procedure.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um procedimento com este nome."))
        return name


class OrcamentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Estimate
        fields = ["patient", "practitioner", "date", "validade", "notes"]
        widgets = {
            "patient": forms.HiddenInput,
            "date": DATA,
            "validade": DATA,
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = Patient.objects.filter(arquivado=False)
        self.fields["patient"].error_messages["required"] = _("Escolha o paciente.")
        self.fields["practitioner"].queryset = Practitioner.objects.filter(active=True)

    def clean(self):
        dados = super().clean()
        if dados.get("date") and dados.get("validade") and dados["validade"] < dados["date"]:
            self.add_error("validade", _("A validade não pode ser antes da data do orçamento."))
        return dados


class ItemForm(FormularioBootstrap, forms.ModelForm):
    """One line of the estimate; price and description come from the procedure if empty."""

    valor_unitario = _campo_dinheiro(_("Valor unitário"), obrigatorio=False)

    class Meta:
        model = EstimateItem
        fields = ["procedimento", "description", "dentes", "faces", "quantidade", "valor_unitario"]
        widgets = {"dentes": forms.HiddenInput}

    def __init__(self, *args, odontologia=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.odontologia = odontologia
        self.fields["procedimento"].queryset = Procedure.objects.filter(active=True)
        self.fields["description"].required = False
        if not odontologia:
            # Teeth and faces belong to the dental module (decision 080).
            del self.fields["dentes"], self.fields["faces"]

    def clean_dentes(self):
        partes = [p.strip() for p in (self.cleaned_data.get("dentes") or "").split(",")]
        dentes = sorted({int(p) for p in partes if p.isdecimal()})
        if any(d not in DENTES_VALIDOS for d in dentes):
            raise forms.ValidationError(_("Dente inválido."))
        return ",".join(str(d) for d in dentes)

    def clean(self):
        dados = super().clean()
        procedimento = dados.get("procedimento")
        if not self.odontologia and any(
            self.data.get(self.add_prefix(campo), "").strip() for campo in ("dentes", "faces")
        ):
            raise forms.ValidationError(_("Habilite Odontologia para registrar dentes ou faces."))
        # The procedure's code is copied, like its description and price.
        self.instance.code = procedimento.code if procedimento else ""
        if not (dados.get("description") or "").strip():
            if procedimento is None:
                self.add_error("description", _("Escolha um procedimento ou descreva o item."))
            else:
                dados["description"] = procedimento.name
        if dados.get("valor_unitario") is None:
            if procedimento is None:
                self.add_error("valor_unitario", _("Informe o valor."))
            else:
                dados["valor_unitario"] = procedimento.amount
        return dados


class DescontoForm(FormularioBootstrap, forms.Form):
    desconto = _campo_dinheiro(_("Desconto no total"), obrigatorio=False)


class AprovarForm(FormularioBootstrap, forms.Form):
    parcelas = forms.IntegerField(
        label=_("Número de parcelas"), min_value=1, max_value=48, initial=1
    )
    primeiro_vencimento = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATA, initial=timezone.localdate
    )
    categoria = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    recebido_agora = forms.BooleanField(label=_("A 1ª parcela já foi paga agora"), required=False)
    forma = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_formas_com_vazio,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Category.objects.filter(
            kind=Category.Tipo.RECEITA, active=True
        )
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)

    def clean(self):
        dados = super().clean()
        if dados.get("recebido_agora"):
            for campo in ("forma", "account"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados
