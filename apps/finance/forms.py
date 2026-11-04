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
    centros = CostCenter.objects.filter(ativo=True)
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
    conta = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = [
            "paciente",
            "pessoa",
            "descricao",
            "categoria",
            "centro_custo",
            "profissional",
            "observacoes",
        ]
        widgets = {
            "paciente": forms.HiddenInput,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {"pessoa": _("Só se quem paga não for um paciente cadastrado.")}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.tipo = Entry.Tipo.RECEBER
        self.fields["paciente"].queryset = Patient.objects.filter(arquivado=False)
        self.fields["categoria"].queryset = Category.objects.filter(
            tipo=Category.Tipo.RECEITA, ativa=True
        )
        self.fields["profissional"].queryset = Practitioner.objects.filter(ativo=True)
        self.fields["conta"].queryset = FinancialAccount.objects.filter(ativa=True)
        _centros_de_custo(self)

    def clean(self):
        dados = super().clean()
        if not dados.get("paciente") and not (dados.get("pessoa") or "").strip():
            self.add_error("pessoa", _("Escolha o paciente ou informe quem paga."))
        if dados.get("valor_total") is not None and dados["valor_total"] <= 0:
            self.add_error("valor_total", _("Informe um valor maior que zero."))
        if dados.get("recebido_agora"):
            for campo in ("forma", "conta"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados


class LancamentoPagarForm(FormularioBootstrap, forms.ModelForm):
    """New payable: one bill split into installments, or the same amount every month."""

    DIVIDIR = "dividir"
    REPETIR = "repetir"

    valor = _campo_dinheiro(_("Valor"))
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
    conta = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = ["fornecedor", "pessoa", "descricao", "categoria", "centro_custo", "observacoes"]
        labels = {"pessoa": _("Fornecedor sem cadastro")}
        help_texts = {"pessoa": _("Só para um pagamento avulso, sem cadastrar o fornecedor.")}
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.tipo = Entry.Tipo.PAGAR
        self.fields["fornecedor"].queryset = Supplier.objects.filter(ativo=True)
        self.fields["categoria"].queryset = Category.objects.filter(
            tipo=Category.Tipo.DESPESA, ativa=True
        )
        self.fields["conta"].queryset = FinancialAccount.objects.filter(ativa=True)
        _centros_de_custo(self)

    def clean(self):
        dados = super().clean()
        if dados.get("fornecedor"):
            dados["pessoa"] = dados["fornecedor"].nome
        elif not (dados.get("pessoa") or "").strip():
            self.add_error("fornecedor", _("Escolha o fornecedor ou informe para quem é."))
        if dados.get("valor") is not None and dados["valor"] <= 0:
            self.add_error("valor", _("Informe um valor maior que zero."))
        if dados.get("pago_agora"):
            for campo in ("forma", "conta"):
                if not dados.get(campo):
                    self.add_error(campo, _("Informe para registrar o pagamento."))
        return dados

    def valor_total(self):
        dados = self.cleaned_data
        if dados["modo"] == self.REPETIR:
            return dados["valor"] * dados["parcelas"]
        return dados["valor"]


class FornecedorForm(FormularioBootstrap, forms.ModelForm):
    """A supplier (decision 093). Documents and phones are typed with or without punctuation."""

    cpf_cnpj = campo_documento()
    telefone = forms.CharField(
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
            "tipo",
            "nome",
            "razao_social",
            "cpf_cnpj",
            "telefone",
            "whatsapp",
            "email",
            "observacoes",
            "ativo",
        ]
        widgets = {"tipo": forms.RadioSelect, "observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        # The country's tax document of an individual or a company (decision 121).
        self.documentos = identification.do_pais(countries.pais_da_clinica(clinic))
        documento_por_tipo(
            self.fields["cpf_cnpj"],
            self.documentos.pessoa,
            self.documentos.empresa,
            self["tipo"].value(),
        )

    def _telefone(self, nome):
        return normalizar_telefone(self.cleaned_data.get(nome))

    def clean_telefone(self):
        return self._telefone("telefone")

    def clean_whatsapp(self):
        return self._telefone("whatsapp")

    def clean(self):
        dados = super().clean()
        # A type without a document in this country (an individual in the UK) keeps none.
        juridica = dados.get("tipo") == Supplier.Tipo.JURIDICA
        do_tipo = self.documentos.empresa if juridica else self.documentos.pessoa
        documento = ""
        if do_tipo is not None:
            try:
                documento = identification.limpar(
                    dados.get("cpf_cnpj", ""), [do_tipo], do_tipo.sigla
                )
            except ValidationError as erro:
                self.add_error("cpf_cnpj", erro)
                return dados
        dados["cpf_cnpj"] = documento
        if (
            documento
            and Supplier.objects.filter(cpf_cnpj=documento).exclude(pk=self.instance.pk).exists()
        ):
            self.add_error("cpf_cnpj", _("Já existe um fornecedor com este documento."))
        return dados


class PlanejamentoForm(FormularioBootstrap, forms.Form):
    """One goal field per group of the chart of accounts (decision 098)."""

    def __init__(self, *args, grupos, metas, **kwargs):
        super().__init__(*args, **kwargs)
        self.grupos = grupos
        for grupo in grupos:
            # Rendered by the field itself: it shows 1.000,00 in Portuguese and reads it back.
            campo = _campo_dinheiro(str(grupo), obrigatorio=False, initial=metas.get(grupo.pk))
            campo.widget.attrs.update(
                {"class": "form-control form-control-sm text-end", "aria-label": str(grupo)}
            )
            self.fields[self.nome(grupo)] = campo

    @staticmethod
    def nome(grupo):
        return f"meta-{grupo.pk}"

    def valores(self):
        return {grupo: self.cleaned_data.get(self.nome(grupo)) for grupo in self.grupos}


class FecharForm(FormularioBootstrap, forms.Form):
    ate = forms.DateField(
        label=_("Fechar até"),
        widget=DATA,
        help_text=_("Último dia do período fechado (no máximo ontem)."),
    )


class ReabrirForm(FormularioBootstrap, forms.Form):
    ate = forms.DateField(
        label=_("Deixar fechado até"),
        widget=DATA,
        required=False,
        help_text=_("Uma data anterior ao fechamento atual. Em branco, reabre tudo."),
    )
    motivo = forms.CharField(label=_("Motivo"), max_length=200)


class ReceberForm(FormularioBootstrap, forms.ModelForm):
    """Payment of an installment. Discounts only for those allowed (administrators)."""

    valor = _campo_dinheiro(_("Valor recebido"))
    juros = _campo_dinheiro(
        _("Juros e multa"), obrigatorio=False, help_text=_("Já incluídos no valor recebido.")
    )
    desconto = _campo_dinheiro(_("Desconto"), obrigatorio=False)

    class Meta:
        model = Payment
        fields = [
            "data",
            "valor",
            "juros",
            "desconto",
            "forma",
            "conta",
            "cartao_bandeira",
            "cartao_parcelas",
            "cartao_codigo",
            "observacao",
        ]
        widgets = {"data": DATA}

    def __init__(self, *args, pode_dar_desconto, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["forma"].choices = _formas_com_vazio()
        self.fields["conta"].queryset = FinancialAccount.objects.filter(ativa=True)
        if not pode_dar_desconto:
            del self.fields["desconto"]
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
        if "desconto" in self.fields:  # removed for those who may not give discounts
            dados["desconto"] = dados.get("desconto") or 0
        if dados.get("valor") is not None and dados["valor"] <= 0:
            self.add_error("valor", _("Informe um valor maior que zero."))
        if (
            dados.get("forma") not in payment_methods.CARTOES
            or "cartao_parcelas" not in self.fields
        ):
            dados["cartao_parcelas"] = None
        if dados.get("forma") not in payment_methods.CARTOES:
            dados["cartao_bandeira"] = dados["cartao_codigo"] = ""
        return dados


class MotivoForm(FormularioBootstrap, forms.Form):
    motivo = forms.CharField(label=_("Motivo"), max_length=200)


def _grupos(excluir=()):
    """Groups as choices, numbered without one query per level."""
    grupos = ligar_grupos(AccountGroup.objects.exclude(pk__in=excluir))
    return [("", "—"), *((g.pk, f"{g.get_tipo_display()} · {g}") for g in grupos)]


class GrupoContabilForm(FormularioBootstrap, forms.ModelForm):
    """A group of the chart of accounts (decision 097)."""

    pai = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo acima")
    )

    class Meta:
        model = AccountGroup
        fields = ["nome", "tipo", "pai", "codigo", "ativo"]
        help_texts = {
            "codigo": _(
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
        pai, tipo = dados.get("pai"), dados.get("tipo")
        if pai and tipo and pai.tipo != tipo:
            self.add_error(
                "pai", _("O grupo acima precisa ser do mesmo tipo (receita ou despesa).")
            )
        nome = (dados.get("nome") or "").strip()
        repetido = AccountGroup.objects.filter(tipo=tipo, pai=pai, nome__iexact=nome)
        if nome and repetido.exclude(pk=self.instance.pk).exists():
            self.add_error("nome", _("Já existe um grupo com este nome neste lugar do plano."))
        if dados.get("codigo") is None and tipo:
            # Left blank where the neighbors are numbered: the next number, so the new group
            # reads "1.3" like the rest instead of having none (review stage 3).
            vizinhos = AccountGroup.objects.filter(tipo=tipo, pai=pai).exclude(pk=self.instance.pk)
            codigos = [c for c in vizinhos.values_list("codigo", flat=True) if c is not None]
            if codigos or (pai is not None and pai.codigo is not None):
                dados["codigo"] = max(codigos, default=0) + 1
        return dados


class CategoriaForm(FormularioBootstrap, forms.ModelForm):
    grupo = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo")
    )

    class Meta:
        model = Category
        fields = ["nome", "tipo", "grupo", "ativa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].queryset = AccountGroup.objects.all()
        self.fields["grupo"].choices = _grupos()
        self.fields["grupo"].help_text = _("Onde a categoria fica no plano de contas (opcional).")

    def clean(self):
        dados = super().clean()
        grupo = dados.get("grupo")
        if grupo and dados.get("tipo") and grupo.tipo != dados["tipo"]:
            self.add_error("grupo", _("O grupo precisa ser do mesmo tipo da categoria."))
        repetida = Category.objects.filter(nome=dados.get("nome"), tipo=dados.get("tipo"))
        if repetida.exclude(pk=self.instance.pk).exists():
            self.add_error("nome", _("Já existe uma categoria com este nome."))
        return dados


class CentroCustoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ["nome", "ativo"]

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if CostCenter.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um centro de custo com este nome."))
        return nome


class ContaForm(FormularioBootstrap, forms.ModelForm):
    saldo_inicial = _campo_dinheiro(
        _("Saldo inicial"),
        obrigatorio=False,
        minimo=None,  # an overdrawn bank account starts negative
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
    )

    class Meta:
        model = FinancialAccount
        fields = ["nome", "tipo", "saldo_inicial", "ativa"]

    def clean_saldo_inicial(self):
        return self.cleaned_data.get("saldo_inicial") or 0

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        if FinancialAccount.objects.filter(nome=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe uma conta com este nome."))
        return nome


class AbrirCaixaForm(FormularioBootstrap, forms.Form):
    valor = _campo_dinheiro(
        _("Valor contado na gaveta"), help_text=_("Conte o dinheiro antes de abrir o caixa.")
    )


class MovimentoCaixaForm(FormularioBootstrap, forms.Form):
    valor = _campo_dinheiro(_("Valor"))
    outra_conta = forms.ModelChoiceField(
        label=_("Outra conta"),
        queryset=FinancialAccount.objects.none(),
        required=False,
        help_text=_("Ex.: depósito no Banco. Vazio: o dinheiro sai do sistema ou vem de fora."),
    )
    motivo = forms.CharField(label=_("Motivo"), max_length=200)

    def __init__(self, *args, caixa, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["outra_conta"].queryset = FinancialAccount.objects.filter(ativa=True).exclude(
            pk=caixa.conta_id
        )

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor <= 0:
            raise forms.ValidationError(_("Informe um valor maior que zero."))
        return valor


class FecharCaixaForm(FormularioBootstrap, forms.Form):
    valor_contado = _campo_dinheiro(_("Valor contado na gaveta"))
    observacao = forms.CharField(
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
    categoria = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Category.objects.filter(
            tipo=Category.Tipo.DESPESA, ativa=True
        )


TAMANHO_MAXIMO_OFX = 5 * 1024 * 1024


class ImportarExtratoForm(FormularioBootstrap, forms.Form):
    conta = forms.ModelChoiceField(label=_("Conta"), queryset=FinancialAccount.objects.none())
    arquivo = forms.FileField(
        label=_("Arquivo OFX"),
        help_text=_("Exporte no site ou aplicativo do banco, no formato OFX (Money)."),
        widget=forms.ClearableFileInput(attrs={"accept": ".ofx,.OFX"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta"].queryset = FinancialAccount.objects.filter(ativa=True)
        banco = FinancialAccount.objects.filter(
            ativa=True, tipo=FinancialAccount.Tipo.BANCO
        ).first()
        if banco is not None:
            self.fields["conta"].initial = banco.pk

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > TAMANHO_MAXIMO_OFX:
            raise forms.ValidationError(_("O arquivo passa de 5 MB."))
        return arquivo


class LancamentoDaTransacaoForm(FormularioBootstrap, forms.Form):
    """A new entry, already paid, for a statement line (a bank fee, an unrecorded Pix)."""

    descricao = forms.CharField(label=_("Descrição"), max_length=200)
    categoria = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
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
        tipo = Category.Tipo.RECEITA if entrada else Category.Tipo.DESPESA
        self.fields["categoria"].queryset = Category.objects.filter(tipo=tipo, ativa=True)
