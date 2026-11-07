from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import BootstrapForm, LocalizedDecimalField, document_by_kind, document_field
from apps.core.validators import normalize_phone
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
from .services import link_groups


def _methods_with_blank():
    """The clinic's country's payment methods (decision 123), after an empty choice."""
    return [("", "—"), *Payment.Method.in_use()]


def _money_field(label, required=True, minimum=0, **extra):
    """Amount typed in the user's format (1.500,50 in Portuguese and Spanish)."""
    return LocalizedDecimalField(
        label=label,
        max_digits=12,
        decimal_places=2,
        min_value=minimum,
        required=required,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
        **extra,
    )


DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _cost_centers(form):
    """The cost center field shows up only once the clinic has one (decision 095)."""
    cost_centers = CostCenter.objects.filter(active=True)
    if cost_centers.exists():
        form.fields["cost_center"].queryset = cost_centers
    else:
        del form.fields["cost_center"]


class ReceivableEntryForm(BootstrapForm, forms.ModelForm):
    """New receivable, split into equal monthly installments (optionally paid now)."""

    total_amount = _money_field(_("Valor total"))
    installments = forms.IntegerField(
        label=_("Número de parcelas"),
        min_value=1,
        max_value=48,
        initial=1,
        help_text=_("Parcelas mensais de mesmo valor. Parcelado no cartão é 1 parcela aqui."),
    )
    first_due_date = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATE_INPUT, initial=timezone.localdate
    )
    received_now = forms.BooleanField(label=_("A 1ª parcela já foi paga agora"), required=False)
    method = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_methods_with_blank,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = [
            "patient",
            "payer",
            "description",
            "category",
            "cost_center",
            "practitioner",
            "notes",
        ]
        widgets = {
            "patient": forms.HiddenInput,
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {"payer": _("Só se quem paga não for um paciente cadastrado.")}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.kind = Entry.Kind.RECEIVABLE
        self.fields["patient"].queryset = Patient.objects.filter(archived=False)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Kind.INCOME, active=True
        )
        self.fields["practitioner"].queryset = Practitioner.objects.filter(active=True)
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        _cost_centers(self)

    def clean(self):
        data = super().clean()
        if not data.get("patient") and not (data.get("payer") or "").strip():
            self.add_error("payer", _("Escolha o paciente ou informe quem paga."))
        if data.get("total_amount") is not None and data["total_amount"] <= 0:
            self.add_error("total_amount", _("Informe um valor maior que zero."))
        if data.get("received_now"):
            for field in ("method", "account"):
                if not data.get(field):
                    self.add_error(field, _("Informe para registrar o pagamento."))
        return data


class PayableEntryForm(BootstrapForm, forms.ModelForm):
    """New payable: one bill split into installments, or the same amount every month."""

    SPLIT = "split"
    REPEAT = "repeat"

    amount = _money_field(_("Valor"))
    mode = forms.ChoiceField(
        label=_("O valor é"),
        choices=[
            (SPLIT, _("o total, dividido nas parcelas")),
            (REPEAT, _("de cada mês (conta fixa, como o aluguel)")),
        ],
        initial=SPLIT,
        widget=forms.RadioSelect,
    )
    installments = forms.IntegerField(
        label=_("Número de parcelas ou de meses"), min_value=1, max_value=48, initial=1
    )
    first_due_date = forms.DateField(
        label=_("Vencimento da 1ª parcela"), widget=DATE_INPUT, initial=timezone.localdate
    )
    paid_now = forms.BooleanField(label=_("A 1ª parcela já foi paga"), required=False)
    method = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=_methods_with_blank,
        required=False,
    )
    account = forms.ModelChoiceField(
        label=_("Conta"), queryset=FinancialAccount.objects.none(), required=False
    )

    class Meta:
        model = Entry
        fields = ["supplier", "payer", "description", "category", "cost_center", "notes"]
        labels = {"payer": _("Fornecedor sem cadastro")}
        help_texts = {"payer": _("Só para um pagamento avulso, sem cadastrar o fornecedor.")}
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.clinic = clinic
        self.instance.kind = Entry.Kind.PAYABLE
        self.fields["supplier"].queryset = Supplier.objects.filter(active=True)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Kind.EXPENSE, active=True
        )
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        _cost_centers(self)

    def clean(self):
        data = super().clean()
        if data.get("supplier"):
            data["payer"] = data["supplier"].name
        elif not (data.get("payer") or "").strip():
            self.add_error("supplier", _("Escolha o fornecedor ou informe para quem é."))
        if data.get("amount") is not None and data["amount"] <= 0:
            self.add_error("amount", _("Informe um valor maior que zero."))
        if data.get("paid_now"):
            for field in ("method", "account"):
                if not data.get(field):
                    self.add_error(field, _("Informe para registrar o pagamento."))
        return data

    def total_amount(self):
        data = self.cleaned_data
        if data["mode"] == self.REPEAT:
            return data["amount"] * data["installments"]
        return data["amount"]


class SupplierForm(BootstrapForm, forms.ModelForm):
    """A supplier (decision 093). Documents and phones are typed with or without punctuation."""

    tax_id = document_field()
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
        self.documents = identification.for_country(countries.clinic_country(clinic))
        document_by_kind(
            self.fields["tax_id"],
            self.documents.person,
            self.documents.company,
            self["kind"].value(),
        )

    def _phone(self, name):
        return normalize_phone(self.cleaned_data.get(name))

    def clean_phone(self):
        return self._phone("phone")

    def clean_whatsapp(self):
        return self._phone("whatsapp")

    def clean(self):
        data = super().clean()
        # A type without a document in this country (an individual in the UK) keeps none.
        is_company = data.get("kind") == Supplier.Kind.COMPANY
        of_kind = self.documents.company if is_company else self.documents.person
        document = ""
        if of_kind is not None:
            try:
                document = identification.clean_value(
                    data.get("tax_id", ""), [of_kind], of_kind.abbreviation
                )
            except ValidationError as error:
                self.add_error("tax_id", error)
                return data
        data["tax_id"] = document
        if (
            document
            and Supplier.objects.filter(tax_id=document).exclude(pk=self.instance.pk).exists()
        ):
            self.add_error("tax_id", _("Já existe um fornecedor com este documento."))
        return data


class PlanningForm(BootstrapForm, forms.Form):
    """One goal field per group of the chart of accounts (decision 098)."""

    def __init__(self, *args, groups, goals, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = groups
        for group in groups:
            # Rendered by the field itself: it shows 1.000,00 in Portuguese and reads it back.
            field = _money_field(str(group), required=False, initial=goals.get(group.pk))
            field.widget.attrs.update(
                {"class": "form-control form-control-sm text-end", "aria-label": str(group)}
            )
            self.fields[self.name(group)] = field

    @staticmethod
    def name(group):
        return f"meta-{group.pk}"

    def paid_and_balance(self):
        return {group: self.cleaned_data.get(self.name(group)) for group in self.groups}


class CloseBooksForm(BootstrapForm, forms.Form):
    until = forms.DateField(
        label=_("Fechar até"),
        widget=DATE_INPUT,
        help_text=_("Último dia do período fechado (no máximo ontem)."),
    )


class ReopenBooksForm(BootstrapForm, forms.Form):
    until = forms.DateField(
        label=_("Deixar fechado até"),
        widget=DATE_INPUT,
        required=False,
        help_text=_("Uma data anterior ao fechamento atual. Em branco, reabre tudo."),
    )
    reason = forms.CharField(label=_("Motivo"), max_length=200)


class ReceivePaymentForm(BootstrapForm, forms.ModelForm):
    """Payment of an installment. Discounts only for those allowed (administrators)."""

    amount = _money_field(_("Valor recebido"))
    interest = _money_field(
        _("Juros e multa"), required=False, help_text=_("Já incluídos no valor recebido.")
    )
    discount = _money_field(_("Desconto"), required=False)

    class Meta:
        model = Payment
        fields = [
            "date",
            "amount",
            "interest",
            "discount",
            "method",
            "account",
            "card_brand",
            "card_installments",
            "card_transaction_code",
            "note",
        ]
        widgets = {"date": DATE_INPUT}

    def __init__(self, *args, can_give_discount, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method"].choices = _methods_with_blank()
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        if not can_give_discount:
            del self.fields["discount"]
        # Card installments and the transaction code's local name (NSU) depend on the country.
        for_country = payment_methods.for_country()
        if not for_country.card_installments:
            del self.fields["card_installments"]
        label = _("Código da transação")
        if for_country.card_code:
            label = f"{label} ({for_country.card_code})"
        self.fields["card_transaction_code"].label = label

    def clean(self):
        data = super().clean()
        data["interest"] = data.get("interest") or 0
        if "discount" in self.fields:  # removed for those who may not give discounts
            data["discount"] = data.get("discount") or 0
        if data.get("amount") is not None and data["amount"] <= 0:
            self.add_error("amount", _("Informe um valor maior que zero."))
        if (
            data.get("method") not in payment_methods.CARDS
            or "card_installments" not in self.fields
        ):
            data["card_installments"] = None
        if data.get("method") not in payment_methods.CARDS:
            data["card_brand"] = data["card_transaction_code"] = ""
        return data


class ReasonForm(BootstrapForm, forms.Form):
    reason = forms.CharField(label=_("Motivo"), max_length=200)


def _groups(exclude=()):
    """Groups as choices, numbered without one query per level."""
    groups = link_groups(AccountGroup.objects.exclude(pk__in=exclude))
    return [("", "—"), *((g.pk, f"{g.get_kind_display()} · {g}") for g in groups)]


class AccountGroupForm(BootstrapForm, forms.ModelForm):
    """A group of the chart of accounts (decision 097)."""

    parent = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo acima")
    )

    class Meta:
        model = AccountGroup
        fields = ["name", "kind", "parent", "code", "active"]
        help_texts = {
            "code": _(
                "Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1. "
                "Em branco: o próximo número."
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A group cannot go under itself or under one of its own subgroups.
        forbidden = {self.instance.pk, *self._descendants()} if self.instance.pk else set()
        self.fields["parent"].queryset = AccountGroup.objects.exclude(pk__in=forbidden)
        self.fields["parent"].choices = _groups(exclude=forbidden)

    def _descendants(self):
        found, queue = set(), [self.instance.pk]
        while queue:
            children = set(
                AccountGroup.objects.filter(parent__in=queue).values_list("pk", flat=True)
            )
            queue = list(children - found)
            found |= children
        return found

    def clean(self):
        data = super().clean()
        parent, kind = data.get("parent"), data.get("kind")
        if parent and kind and parent.kind != kind:
            self.add_error(
                "parent", _("O grupo acima precisa ser do mesmo tipo (receita ou despesa).")
            )
        name = (data.get("name") or "").strip()
        repeated = AccountGroup.objects.filter(kind=kind, parent=parent, name__iexact=name)
        if name and repeated.exclude(pk=self.instance.pk).exists():
            self.add_error("name", _("Já existe um grupo com este nome neste lugar do plano."))
        if data.get("code") is None and kind:
            # Left blank where the neighbors are numbered: the next number, so the new group
            # reads "1.3" like the rest instead of having none (review stage 3).
            neighbors = AccountGroup.objects.filter(kind=kind, parent=parent).exclude(
                pk=self.instance.pk
            )
            codes = [c for c in neighbors.values_list("code", flat=True) if c is not None]
            if codes or (parent is not None and parent.code is not None):
                data["code"] = max(codes, default=0) + 1
        return data


class CategoryForm(BootstrapForm, forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=AccountGroup.objects.none(), required=False, label=_("Grupo")
    )

    class Meta:
        model = Category
        fields = ["name", "kind", "group", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = AccountGroup.objects.all()
        self.fields["group"].choices = _groups()
        self.fields["group"].help_text = _("Onde a categoria fica no plano de contas (opcional).")

    def clean(self):
        data = super().clean()
        group = data.get("group")
        if group and data.get("kind") and group.kind != data["kind"]:
            self.add_error("group", _("O grupo precisa ser do mesmo tipo da categoria."))
        repeated_one = Category.objects.filter(name=data.get("name"), kind=data.get("kind"))
        if repeated_one.exclude(pk=self.instance.pk).exists():
            self.add_error("name", _("Já existe uma categoria com este nome."))
        return data


class CostCenterForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ["name", "active"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if CostCenter.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um centro de custo com este nome."))
        return name


class FinancialAccountForm(BootstrapForm, forms.ModelForm):
    opening_balance = _money_field(
        _("Saldo inicial"),
        required=False,
        minimum=None,  # an overdrawn bank account starts negative
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
    )

    class Meta:
        model = FinancialAccount
        fields = ["name", "kind", "opening_balance", "active"]

    def clean_opening_balance(self):
        return self.cleaned_data.get("opening_balance") or 0

    def clean_name(self):
        name = self.cleaned_data["name"]
        if FinancialAccount.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe uma conta com este nome."))
        return name


class OpenCashRegisterForm(BootstrapForm, forms.Form):
    amount = _money_field(
        _("Valor contado na gaveta"), help_text=_("Conte o dinheiro antes de abrir o caixa.")
    )


class CashMovementForm(BootstrapForm, forms.Form):
    amount = _money_field(_("Valor"))
    other_account = forms.ModelChoiceField(
        label=_("Outra conta"),
        queryset=FinancialAccount.objects.none(),
        required=False,
        help_text=_("Ex.: depósito no Banco. Vazio: o dinheiro sai do sistema ou vem de fora."),
    )
    reason = forms.CharField(label=_("Motivo"), max_length=200)

    def __init__(self, *args, cash_register, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["other_account"].queryset = FinancialAccount.objects.filter(
            active=True
        ).exclude(pk=cash_register.account_id)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError(_("Informe um valor maior que zero."))
        return amount


class CloseCashRegisterForm(BootstrapForm, forms.Form):
    counted_amount = _money_field(_("Valor contado na gaveta"))
    note = forms.CharField(
        label=_("Observação"),
        max_length=200,
        required=False,
        help_text=_("Explique a diferença, se houver."),
    )


class CommissionPercentageForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Practitioner
        fields = ["commission_percentage"]
        localized_fields = ["commission_percentage"]


class PayCommissionForm(BootstrapForm, forms.Form):
    due_date = forms.DateField(label=_("Vencimento"), widget=DATE_INPUT, initial=timezone.localdate)
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            kind=Category.Kind.EXPENSE, active=True
        )


MAX_OFX_SIZE = 5 * 1024 * 1024


class ImportStatementForm(BootstrapForm, forms.Form):
    account = forms.ModelChoiceField(label=_("Conta"), queryset=FinancialAccount.objects.none())
    file = forms.FileField(
        label=_("Arquivo OFX"),
        help_text=_("Exporte no site ou aplicativo do banco, no formato OFX (Money)."),
        widget=forms.ClearableFileInput(attrs={"accept": ".ofx,.OFX"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = FinancialAccount.objects.filter(active=True)
        bank = FinancialAccount.objects.filter(active=True, kind=FinancialAccount.Kind.BANK).first()
        if bank is not None:
            self.fields["account"].initial = bank.pk

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_OFX_SIZE:
            raise forms.ValidationError(_("O arquivo passa de 5 MB."))
        return file


class TransactionEntryForm(BootstrapForm, forms.Form):
    """A new entry, already paid, for a statement line (a bank fee, an unrecorded Pix)."""

    description = forms.CharField(label=_("Descrição"), max_length=200)
    category = forms.ModelChoiceField(label=_("Categoria"), queryset=Category.objects.none())
    payer = forms.CharField(
        label=_("Pagador ou fornecedor"),
        max_length=200,
        required=False,
        help_text=_("Se ficar em branco, vale a descrição."),
    )
    method = forms.ChoiceField(
        label=_("Forma de pagamento"),
        choices=Payment.Method.in_use,
        initial=Payment.Method.TRANSFER,
    )

    def __init__(self, *args, is_incoming, **kwargs):
        super().__init__(*args, **kwargs)
        kind = Category.Kind.INCOME if is_incoming else Category.Kind.EXPENSE
        self.fields["category"].queryset = Category.objects.filter(kind=kind, active=True)
