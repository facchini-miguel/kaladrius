from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.financeiro.forms import DATA, _campo_dinheiro
from apps.financeiro.models import Categoria, Conta, Pagamento
from apps.odontologia.dentes import DENTES_VALIDOS
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from .models import ItemOrcamento, Orcamento, Procedimento


class ProcedimentoForm(FormularioBootstrap, forms.ModelForm):
    valor = _campo_dinheiro(_("Valor"))

    class Meta:
        model = Procedimento
        fields = ["nome", "valor", "categoria", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.filter(
            tipo=Categoria.Tipo.RECEITA, ativa=True
        )

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        if Procedimento.objects.filter(nome=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um procedimento com este nome."))
        return nome


class OrcamentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = ["paciente", "profissional", "data", "validade", "observacoes"]
        widgets = {
            "paciente": forms.HiddenInput,
            "data": DATA,
            "validade": DATA,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(arquivado=False)
        self.fields["paciente"].error_messages["required"] = _("Escolha o paciente.")
        self.fields["profissional"].queryset = Profissional.objects.filter(ativo=True)

    def clean(self):
        dados = super().clean()
        if dados.get("data") and dados.get("validade") and dados["validade"] < dados["data"]:
            self.add_error("validade", _("A validade não pode ser antes da data do orçamento."))
        return dados


class ItemForm(FormularioBootstrap, forms.ModelForm):
    """One line of the estimate; price and description come from the procedure if empty."""

    valor_unitario = _campo_dinheiro(_("Valor unitário"), obrigatorio=False)

    class Meta:
        model = ItemOrcamento
        fields = ["procedimento", "descricao", "dentes", "faces", "quantidade", "valor_unitario"]
        widgets = {"dentes": forms.HiddenInput}

    def __init__(self, *args, odontologia=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.odontologia = odontologia
        self.fields["procedimento"].queryset = Procedimento.objects.filter(ativo=True)
        self.fields["descricao"].required = False
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
        if not (dados.get("descricao") or "").strip():
            if procedimento is None:
                self.add_error("descricao", _("Escolha um procedimento ou descreva o item."))
            else:
                dados["descricao"] = procedimento.nome
        if dados.get("valor_unitario") is None:
            if procedimento is None:
                self.add_error("valor_unitario", _("Informe o valor."))
            else:
                dados["valor_unitario"] = procedimento.valor
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
    categoria = forms.ModelChoiceField(label=_("Categoria"), queryset=Categoria.objects.none())
    recebido_agora = forms.BooleanField(label=_("A 1ª parcela já foi paga agora"), required=False)
    forma = forms.ChoiceField(
        label=_("Forma de pagamento"), choices=[("", "—"), *Pagamento.Forma.choices], required=False
    )
    conta = forms.ModelChoiceField(label=_("Conta"), queryset=Conta.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.filter(
            tipo=Categoria.Tipo.RECEITA, ativa=True
        )
        self.fields["conta"].queryset = Conta.objects.filter(ativa=True)

    def clean(self):
        dados = super().clean()
        if dados.get("recebido_agora"):
            for campo in ("forma", "conta"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados
