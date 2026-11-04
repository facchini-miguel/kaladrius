from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import CampoDecimal, FormularioBootstrap, campo_documento, documento_por_tipo
from apps.core.validators import normalizar_telefone
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import payment_methods
from .models import (
    AccountGroup,
    Category,
    CostCenter,
    Entry,
    FinancialAccount,
    Payment,
    Supplier,
)
from .services import ligar_grupos


def _formas_com_vazio():
    """The clinic's country's payment methods (decision 123), after an empty choice."""
    return [("", "—"), *Payment.Forma.em_uso()]


def _campo_dinheiro(rotulo, obrigatorio=True, minimo=0, **extra):
    """Amount typed in the user's format (1.500,50 in Portuguese and Spanish)."""
    return CampoDecimal(
        label=rotulo,
        max_digits=12,
        decimal_places=2,
        min_value=minimo,
        required=obrigatorio,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
        **extra,
    )


DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _centros_de_custo(form):
    """The cost center field shows up only once the clinic has one (decision 095)."""
    centros = CostCenter.objects.filter(active=True)
    if centros.exists():
        form.fields["centro_custo"].queryset = centros
    else:
        del form.fields["centro_custo"]


class LancamentoReceberForm(FormularioBootstrap, forms.ModelForm):
    """New receivable, split into equal monthly installments (optionally paid now)."""

    valor_total = _campo_dinheiro(_("Valor total"))
    parcelas = forms.IntegerField(
        label=_("Número de parcelas"),
        min_value=1,
        max_value=48,
        initial=1,
        help_text=_("Parcelas mensais de mesmo valor. Parcelado no cartão é 1 parcela aqui."),
    )
    primeiro_vencimento = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATA, initial=timezone.localdate
    )
    recebido_agora = forms.BooleanField(label=_("A 1ª parcela já foi paga agora"), required=False)
    forma = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_formas_com_vazio,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = [
            "patient",
            "pessoa",
            "description",
            "category",
            "centro_custo",
            "practitioner",
            "notes",
        ]
        widgets = {
            "patient": forms.HiddenInput,
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {"pessoa": _("Só se quem paga não for um paciente cadastrado.")}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.kind = Entry.Tipo.RECEBER
        self.fields["patient"].queryset = Patient.objects.filter(arquivado=False)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Tipo.RECEITA, active=True
        )
        self.fields["practitioner"].queryset = Practitioner.objects.filter(active=True)
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        _centros_de_custo(self)

    def clean(self):
        dados = super().clean()
        if not dados.get("patient") and not (dados.get("pessoa") or "").strip():
            self.add_error("pessoa", _("Escolha o paciente ou informe quem paga."))
        if dados.get("valor_total") is not None and dados["valor_total"] <= 0:
            self.add_error("valor_total", _("Informe um valor maior que zero."))
        if dados.get("recebido_agora"):
            for campo in ("forma", "account"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados


class LancamentoPagarForm(FormularioBootstrap, forms.ModelForm):
    """New payable: one bill split into installments, or the same amount every month."""

    DIVIDIR = "dividir"
    REPETIR = "repetir"

    amount = _campo_dinheiro(_("Valor"))
    modo = forms.ChoiceField(
        label=_("O valor é"),
        choices=[
            (DIVIDIR, _("o total, dividido nas parcelas")),
            (REPETIR, _("de cada mês (conta fixa, como o aluguel)")),
        ],
        initial=DIVIDIR,
        widget=forms.RadioSelect,
    )
    parcelas = forms.IntegerField(
        label=_("Número de parcelas ou de meses"), min_value=1, max_value=48, initial=1
    )
    primeiro_vencimento = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATA, initial=timezone.localdate
    )
    pago_agora = forms.BooleanField(label=_("A 1ª parcela já foi paga"), required=False)
    forma = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_formas_com_vazio,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = ["fornecedor", "pessoa", "description", "category", "centro_custo", "notes"]
        labels = {"pessoa": _("Fornecedor sem cadastro")}
        help_texts = {"pessoa": _("Só para um pagamento avulso, sem cadastrar o fornecedor.")}
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.kind = Entry.Tipo.PAGAR
        self.fields["fornecedor"].queryset = Supplier.objects.filter(active=True)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Tipo.DESPESA, active=True
        )
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        _centros_de_custo(self)

    def clean(self):
        dados = super().clean()
        if dados.get("fornecedor"):
            dados["pessoa"] = dados["fornecedor"].name
        elif not (dados.get("pessoa") or "").strip():
            self.add_error("fornecedor", _("Escolha o fornecedor ou informe para quem é."))
        if dados.get("amount") is not None and dados["amount"] <= 0:
            self.add_error("amount", _("Informe um valor maior que zero."))
        if dados.get("pago_agora"):
            for campo in ("forma", "account"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados

    def valor_total(self):
        dados = self.cleaned_data
        if dados["modo"] == self.REPETIR:
            return dados["amount"] * dados["parcelas"]
        return dados["amount"]


class FornecedorForm(FormularioBootstrap, forms.ModelForm):
    """A supplier (decision 093). Documents and phones are typed with or without punctuation."""

    tax_id = campo_documento()
    phone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )
    whatsapp = forms.CharField(
        label=_("WhatsApp"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )

    class Meta:
        model = Supplier
        fields = [
            "kind",
            "name",
            "legal_name",
            "tax_id",
            "phone",
            "whatsapp",
            "email",
            "notes",
            "active",
        ]
        widgets = {"kind": forms.RadioSelect, "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        # The country's tax document of an individual or a company (decision 121).
        self.documentos = identification.do_pais(countries.pais_da_clinica(clinic))
        documento_por_tipo(
            self.fields["tax_id"],
            self.documentos.pessoa,
            self.documentos.empresa,
            self["kind"].value(),
        )

    def _telefone(self, name):
        return normalizar_telefone(self.cleaned_data.get(name))

    def clean_phone(self):
        return self._telefone("phone")

    def clean_whatsapp(self):
        return self._telefone("whatsapp")

    def clean(self):
        dados = super().clean()
        # A type without a document in this country (an individual in the UK) keeps none.
        juridica = dados.get("kind") == Supplier.Tipo.JURIDICA
        do_tipo = self.documentos.empresa if juridica else self.documentos.pessoa
        documento = ""
        if do_tipo is not None:
            try:
                documento = identification.limpar(dados.get("tax_id", ""), [do_tipo], do_tipo.sigla)
            except ValidationError as erro:
                self.add_error("tax_id", erro)
                return dados
        dados["tax_id"] = documento
        if (
            documento
            and Supplier.objects.filter(tax_id=documento).exclude(pk=self.instance.pk).exists()
        ):
            self.add_error("tax_id", _("Já existe um fornecedor com este documento."))
        return dados


class PlanejamentoForm(FormularioBootstrap, forms.Form):
    """One goal field per group of the chart of accounts (decision 098)."""

    def __init__(self, *args, grupos, metas, **kwargs):
        super().__init__(*args, **kwargs)
        self.grupos = grupos
        for group in grupos:
            # Rendered by the field itself: it shows 1.000,00 in Portuguese and reads it back.
            campo = _campo_dinheiro(str(group), obrigatorio=False, initial=metas.get(group.pk))
            campo.widget.attrs.update(
                {"class": "form-control form-control-sm text-end", "aria-label": str(group)}
            )
            self.fields[self.name(group)] = campo

    @staticmethod
    def name(group):
        return f"meta-{group.pk}"

    def valores(self):
        return {group: self.cleaned_data.get(self.name(group)) for group in self.grupos}


class FecharForm(FormularioBootstrap, forms.Form):
    until = forms.DateField(
        label=_("Fechar até"),
        widget=DATA,
        help_text=_("Último dia do período fechado (no máximo ontem)."),
    )


class ReabrirForm(FormularioBootstrap, forms.Form):
    until = forms.DateField(
        label=_("Deixar fechado até"),
        widget=DATA,
        required=False,
        help_text=_("Uma data anterior ao fechamento atual. Em branco, reabre tudo."),
    )
    reason = forms.CharField(label=_("Motivo"), max_length=200)


class ReceberForm(FormularioBootstrap, forms.ModelForm):
    """Payment of an installment. Discounts only for those allowed (administrators)."""

    amount = _campo_dinheiro(_("Valor recebido"))
    juros = _campo_dinheiro(
        _("Juros e multa"), obrigatorio=False, help_text=_("Já incluídos no valor recebido.")
    )
    discount = _campo_dinheiro(_("Desconto"), obrigatorio=False)

    class Meta:
        model = Payment
        fields = [
            "date",
            "amount",
            "juros",
            "discount",
            "forma",
            "account",
            "cartao_bandeira",
            "cartao_parcelas",
            "cartao_codigo",
            "note",
        ]
        widgets = {"date": DATA}

    def __init__(self, *args, pode_dar_desconto, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["forma"].choices = _formas_com_vazio()
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        if not pode_dar_desconto:
            del self.fields["discount"]
        # Card installments and the transaction code's local name (NSU) depend on the country.
        do_pais = payment_methods.do_pais()
        if not do_pais.parcelas_no_cartao:
            del self.fields["cartao_parcelas"]
        rotulo = _("Código da transação")
        if do_pais.codigo_do_cartao:
            rotulo = f"{rotulo} ({do_pais.codigo_do_cartao})"
        self.fields["cartao_codigo"].label = rotulo

    def clean(self):
        dados = super().clean()
        dados["juros"] = dados.get("juros") or 0
        if "discount" in self.fields:  # removed for those who may not give discounts
            dados["discount"] = dados.get("discount") or 0
        if dados.get("amount") is not None and dados["amount"] <= 0:
            self.add_error("amount", _("Informe um valor maior que zero."))
        if (
            dados.get("forma") not in payment_methods.CARTOES
            or "cartao_parcelas" not in self.fields
        ):
            dados["cartao_parcelas"] = None
        if dados.get("forma") not in payment_methods.CARTOES:
            dados["cartao_bandeira"] = dados["cartao_codigo"] = ""
        return dados


class MotivoForm(FormularioBootstrap, forms.Form):
    reason = forms.CharField(label=_("Motivo"), max_length=200)


def _grupos(excluir=()):
    """Groups as choices, numbered without one query per level."""
    grupos = ligar_grupos(AccountGroup.objects.exclude(pk__in=excluir))
    return [("", "—"), *((g.pk, f"{g.get_kind_display()} · {g}") for g in grupos)]


class GrupoContabilForm(FormularioBootstrap, forms.ModelForm):
    """A group of the chart of accounts (decision 097)."""

    pai = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo acima")
    )

    class Meta:
        model = AccountGroup
        fields = ["name", "kind", "pai", "code", "active"]
        help_texts = {
            "code": _(
                "Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1. "
                "Em branco: o próximo número."
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A group cannot go under itself or under one of its own subgroups.
        proibidos = {self.instance.pk, *self._descendentes()} if self.instance.pk else set()
        self.fields["pai"].queryset = AccountGroup.objects.exclude(pk__in=proibidos)
        self.fields["pai"].choices = _grupos(excluir=proibidos)

    def _descendentes(self):
        encontrados, fila = set(), [self.instance.pk]
        while fila:
            filhos = set(AccountGroup.objects.filter(pai__in=fila).values_list("pk", flat=True))
            fila = list(filhos - encontrados)
            encontrados |= filhos
        return encontrados

    def clean(self):
        dados = super().clean()
        pai, kind = dados.get("pai"), dados.get("kind")
        if pai and kind and pai.kind != kind:
            self.add_error(
                "pai", _("O grupo acima precisa ser do mesmo tipo (receita ou despesa).")
            )
        name = (dados.get("name") or "").strip()
        repetido = AccountGroup.objects.filter(kind=kind, pai=pai, name__iexact=name)
        if name and repetido.exclude(pk=self.instance.pk).exists():
            self.add_error("name", _("Já existe um grupo com este nome neste lugar do plano."))
        if dados.get("code") is None and kind:
            # Left blank where the neighbors are numbered: the next number, so the new group
            # reads "1.3" like the rest instead of having none (review stage 3).
            vizinhos = AccountGroup.objects.filter(kind=kind, pai=pai).exclude(pk=self.instance.pk)
            codigos = [c for c in vizinhos.values_list("code", flat=True) if c is not None]
            if codigos or (pai is not None and pai.code is not None):
                dados["code"] = max(codigos, default=0) + 1
        return dados


class CategoriaForm(FormularioBootstrap, forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo")
    )

    class Meta:
        model = Category
        fields = ["name", "kind", "group", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = AccountGroup.objects.all()
        self.fields["group"].choices = _grupos()
        self.fields["group"].help_text = _("Onde a categoria fica no plano de contas (opcional).")

    def clean(self):
        dados = super().clean()
        group = dados.get("group")
        if group and dados.get("kind") and group.kind != dados["kind"]:
            self.add_error("group", _("O grupo precisa ser do mesmo tipo da categoria."))
        repetida = Category.objects.filter(name=dados.get("name"), kind=dados.get("kind"))
        if repetida.exclude(pk=self.instance.pk).exists():
            self.add_error("name", _("Já existe uma categoria com este nome."))
        return dados


class CentroCustoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ["name", "active"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if CostCenter.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um centro de custo com este nome."))
        return name


class ContaForm(FormularioBootstrap, forms.ModelForm):
    saldo_inicial = _campo_dinheiro(
        _("Saldo inicial"),
        obrigatorio=False,
        minimo=None,  # an overdrawn bank account starts negative
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
    )

    class Meta:
        model = FinancialAccount
        fields = ["name", "kind", "saldo_inicial", "active"]

    def clean_saldo_inicial(self):
        return self.cleaned_data.get("saldo_inicial") or 0

    def clean_name(self):
        name = self.cleaned_data["name"]
        if FinancialAccount.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe uma conta com este nome."))
        return name


class AbrirCaixaForm(FormularioBootstrap, forms.Form):
    amount = _campo_dinheiro(
        _("Valor contado na gaveta"), help_text=_("Conte o dinheiro antes de abrir o caixa.")
    )


class MovimentoCaixaForm(FormularioBootstrap, forms.Form):
    amount = _campo_dinheiro(_("Valor"))
    outra_conta = forms.ModelChoiceField(
        label=_("Outra conta"),
        queryset=FinancialAccount.objects.none(),
        required=False,
        help_text=_("Ex.: depósito no Banco. Vazio: o dinheiro sai do sistema ou vem de fora."),
    )
    reason = forms.CharField(label=_("Motivo"), max_length=200)

    def __init__(self, *args, caixa, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["outra_conta"].queryset = FinancialAccount.objects.filter(active=True).exclude(
            pk=caixa.account_id
        )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError(_("Informe um valor maior que zero."))
        return amount


class FecharCaixaForm(FormularioBootstrap, forms.Form):
    valor_contado = _campo_dinheiro(_("Valor contado na gaveta"))
    note = forms.CharField(
        label=_("Observação"),
        max_length=200,
        required=False,
        help_text=_("Explique a diferença, se houver."),
    )


class PercentualComissaoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Practitioner
        fields = ["comissao_percentual"]
        localized_fields = ["comissao_percentual"]


class PagarComissaoForm(FormularioBootstrap, forms.Form):
    vencimento = forms.DateField(label=_("Vencimento"), widget=DATA, initial=timezone.localdate)
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Tipo.DESPESA, active=True
        )


TAMANHO_MAXIMO_OFX = 5 * 1024 * 1024


class ImportarExtratoForm(FormularioBootstrap, forms.Form):
    account = forms.ModelChoiceField(label=_("Conta"), queryset=FinancialAccount.objects.none())
    file = forms.FileField(
        label=_("Arquivo OFX"),
        help_text=_("Exporte no site ou aplicativo do banco, no formato OFX (Money)."),
        widget=forms.ClearableFileInput(attrs={"accept": ".ofx,.OFX"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        banco = FinancialAccount.objects.filter(
            active=True, kind=FinancialAccount.Tipo.BANCO
        ).first()
        if banco is not None:
            self.fields["account"].initial = banco.pk

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > TAMANHO_MAXIMO_OFX:
            raise forms.ValidationError(_("O arquivo passa de 5 MB."))
        return file


class LancamentoDaTransacaoForm(FormularioBootstrap, forms.Form):
    """A new entry, already paid, for a statement line (a bank fee, an unrecorded Pix)."""

    description = forms.CharField(label=_("Descrição"), max_length=200)
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    pessoa = forms.CharField(
        label=_("Pagador ou fornecedor"),
        max_length=200,
        required=False,
        help_text=_("Se ficar em branco, vale a descrição."),
    )
    forma = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=Payment.Forma.em_uso,
        initial=Payment.Forma.TRANSFERENCIA,
    )

    def __init__(self, *args, entrada, **kwargs):
        super().__init__(*args, **kwargs)
        kind = Category.Tipo.RECEITA if entrada else Category.Tipo.DESPESA
        self.fields["category"].queryset = Category.objects.filter(kind=kind, active=True)
