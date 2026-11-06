"""Financial entries recorded by hand (decision 048): who owes what and how they paid.

A Lancamento (receivable or payable) is split into Parcelas (installments); each
Pagamento records money received for one installment, with the method and the account.
Nothing is deleted: entries are cancelled and payments reversed, with a reason. Amounts
are Decimal with cents.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicManager, ClinicModel, without_isolation
from apps.core.ordering import ALPHABETICAL

ZERO = Decimal("0.00")
MONEY = {"max_digits": 12, "decimal_places": 2}


class FinancialAccount(ClinicModel):
    """Where the money goes: the cash drawer, a bank account, the card machine."""

    class Kind(models.TextChoices):
        CASH = "dinheiro", _("Dinheiro (caixa)")
        BANK = "banco", _("Banco")
        CARD = "cartao", _("Maquininha de cartão")

    name = models.CharField(_("nome"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    opening_balance = models.DecimalField(
        _("saldo inicial"),
        default=ZERO,
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
        **MONEY,
    )
    active = models.BooleanField(_("ativa"), default=True)

    class Meta:
        db_table = "finance_financial_account"
        verbose_name = _("conta")
        verbose_name_plural = _("contas")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="financial_account_unique")
        ]

    def __str__(self):
        return self.name


class FinancialKind(models.TextChoices):
    INCOME = "receita", _("Receita")
    EXPENSE = "despesa", _("Despesa")


class AccountGroup(ClinicModel):
    """A node of the chart of accounts (decision 097, legacy Medical grupocontabil):
    groups hold subgroups and categories; entries go to the categories (the leaves)."""

    Kind = FinancialKind

    name = models.CharField(_("nome"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("grupo acima"),
    )
    code = models.PositiveSmallIntegerField(
        _("código"),
        null=True,
        blank=True,
        help_text=_("Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1."),
    )
    active = models.BooleanField(_("ativo"), default=True)

    class Meta:
        db_table = "finance_account_group"
        verbose_name = _("grupo contábil")
        verbose_name_plural = _("grupos contábeis")
        ordering = ["kind", "code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "kind", "parent", "name"], name="account_group_unique"
            )
        ]

    def __str__(self):
        return f"{self.number} {self.name}" if self.number else self.name

    def ancestors(self):
        """From the top group down to the parent of this one."""
        cadeia, current = [], self.parent
        while current is not None:
            cadeia.insert(0, current)
            current = current.parent
        return cadeia

    @property
    def number(self):
        codigos = [g.code for g in [*self.ancestors(), self]]
        return ".".join(map(str, codigos)) if None not in codigos else ""


class Category(ClinicModel):
    """Grouping of income and expenses for the reports."""

    Kind = FinancialKind

    name = models.CharField(_("nome"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categories",
        verbose_name=_("grupo"),
    )
    active = models.BooleanField(_("ativa"), default=True)

    class Meta:
        db_table = "finance_category"
        verbose_name = _("categoria")
        verbose_name_plural = _("categorias")
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "kind", "name"], name="category_unique")
        ]

    def __str__(self):
        return self.name


class CostCenter(ClinicModel):
    """Who in the clinic an entry is for (decision 095): a room, a specialty, the office.

    Optional on every entry, one per entry (no split across centers yet).
    """

    name = models.CharField(_("nome"), max_length=60, db_collation=ALPHABETICAL)
    active = models.BooleanField(_("ativo"), default=True)

    class Meta:
        db_table = "finance_cost_center"
        verbose_name = _("centro de custo")
        verbose_name_plural = _("centros de custo")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="cost_center_unique")
        ]

    def __str__(self):
        return self.name


# Accounts and categories every new clinic starts with (it can add, rename or deactivate).
DEFAULT_ACCOUNTS = [("Caixa", FinancialAccount.Kind.CASH), ("Banco", FinancialAccount.Kind.BANK)]
DEFAULT_CATEGORIES = [
    ("Tratamento", Category.Kind.INCOME),
    ("Consulta", Category.Kind.INCOME),
    ("Outras receitas", Category.Kind.INCOME),
    ("Aluguel", Category.Kind.EXPENSE),
    ("Material odontológico", Category.Kind.EXPENSE),
    ("Laboratório de prótese", Category.Kind.EXPENSE),
    ("Salários e encargos", Category.Kind.EXPENSE),
    ("Comissões", Category.Kind.EXPENSE),
    ("Impostos", Category.Kind.EXPENSE),
    ("Água, luz e internet", Category.Kind.EXPENSE),
    ("Manutenção", Category.Kind.EXPENSE),
    ("Outras despesas", Category.Kind.EXPENSE),
]
# A basic chart of accounts for new clinics (decision 097): code, group and its categories.
DEFAULT_CHART = {
    Category.Kind.INCOME: [
        (1, "Atendimentos", ["Tratamento", "Consulta"]),
        (2, "Outras receitas", ["Outras receitas"]),
    ],
    Category.Kind.EXPENSE: [
        (1, "Ocupação", ["Aluguel", "Água, luz e internet", "Manutenção"]),
        (2, "Pessoal", ["Salários e encargos", "Comissões"]),
        (3, "Materiais e laboratório", ["Material odontológico", "Laboratório de prótese"]),
        (4, "Impostos", ["Impostos"]),
        (5, "Outras despesas", ["Outras despesas"]),
    ],
}


def create_defaults(clinic):
    """Default accounts and categories for a clinic that has none."""
    with without_isolation():
        if not FinancialAccount.objects.filter(clinic=clinic).exists():
            FinancialAccount.objects.bulk_create(
                FinancialAccount(clinic=clinic, name=name, kind=kind)
                for name, kind in DEFAULT_ACCOUNTS
            )
        if not Category.objects.filter(clinic=clinic).exists():
            grupo_de = {}
            for kind, rows in DEFAULT_CHART.items():
                for code, name, categorias in rows:
                    group = AccountGroup.objects.create(
                        clinic=clinic, kind=kind, code=code, name=name
                    )
                    grupo_de.update({(kind, category): group for category in categorias})
            Category.objects.bulk_create(
                Category(clinic=clinic, name=name, kind=kind, group=grupo_de.get((kind, name)))
                for name, kind in DEFAULT_CATEGORIES
            )


class Supplier(ClinicModel):
    """Who the clinic buys from or pays (decision 093), picked on a payable."""

    class Kind(models.TextChoices):
        INDIVIDUAL = "PF", _("Pessoa física")
        COMPANY = "PJ", _("Pessoa jurídica")

    kind = models.CharField(_("tipo"), max_length=2, choices=Kind.choices, default=Kind.COMPANY)
    name = models.CharField(
        _("nome"),
        max_length=200,
        help_text=_("Para pessoa jurídica, o nome fantasia."),
        db_collation=ALPHABETICAL,
    )
    legal_name = models.CharField(_("razão social"), max_length=200, blank=True)
    # The country's tax document (decision 121); the name stayed from Brazil.
    tax_id = models.CharField(_("documento"), max_length=20, blank=True)
    phone = models.CharField(_("telefone"), max_length=11, blank=True)
    whatsapp = models.CharField(_("WhatsApp"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    notes = models.TextField(_("observações"), blank=True)
    active = models.BooleanField(_("ativo"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "finance_supplier"
        verbose_name = _("fornecedor")
        verbose_name_plural = _("fornecedores")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "tax_id"],
                condition=~Q(tax_id=""),
                name="supplier_tax_id_unique_per_clinic",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def document_role(self):
        """Its document's role in apps/core/identification.py."""
        return "empresa" if self.kind == self.Kind.COMPANY else "pessoa"


class Entry(ClinicModel):
    """An amount owed to the clinic (receivable) or by it (payable), in installments."""

    class Kind(models.TextChoices):
        RECEIVABLE = "receber", _("A receber")
        PAYABLE = "pagar", _("A pagar")

    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    description = models.CharField(_("descrição"), max_length=200)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("categoria"),
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("centro de custo"),
    )
    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("paciente"),
    )
    # Who pays (receivable without a registered patient) or the supplier (payable). With a
    # registered supplier it holds the supplier's name, so lists and reports need no join.
    payer = models.CharField(_("pagador"), max_length=200, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("fornecedor"),
    )
    practitioner = models.ForeignKey(
        "profissionais.Practitioner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("profissional"),
        help_text=_("Quem fez o atendimento (opcional)."),
    )
    total_amount = models.DecimalField(_("valor total"), **MONEY)
    date = models.DateField(_("data"), default=timezone.localdate)
    notes = models.TextField(_("observações"), blank=True)
    cancelled = models.BooleanField(_("cancelado"), default=False)
    cancelled_at = models.DateTimeField(_("cancelado em"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cancelado por"),
    )
    cancellation_reason = models.CharField(_("motivo do cancelamento"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "finance_entry"
        verbose_name = _("lançamento")
        verbose_name_plural = _("lançamentos")
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(total_amount__gt=0), name="entry_amount_positive"),
        ]

    def __str__(self):
        return f"{self.description} ({self.payer_name})"

    @property
    def payer_name(self):
        return self.patient.name if self.patient_id else self.payer


class InstallmentQuerySet(models.QuerySet):
    def with_balance(self):
        """Annotate paid (principal paid by non-reversed payments) and balance."""
        principal = ExpressionWrapper(
            F("payments__amount") - F("payments__interest") + F("payments__discount"),
            output_field=DecimalField(**MONEY),
        )
        pago = Coalesce(
            Sum(principal, filter=Q(payments__reversed=False)),
            Value(ZERO),
            output_field=DecimalField(**MONEY),
        )
        return self.annotate(paid=pago).annotate(
            balance=ExpressionWrapper(F("amount") - F("paid"), output_field=DecimalField(**MONEY))
        )

    def unpaid(self):
        """Installments still owed (positive balance) of entries not cancelled."""
        return self.with_balance().filter(balance__gt=0, entry__cancelled=False)


class Installment(ClinicModel):
    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name=_("lançamento"),
    )
    number = models.PositiveSmallIntegerField(_("número"))
    due_date = models.DateField(_("vencimento"))
    amount = models.DecimalField(_("valor"), **MONEY)

    # Same isolation as every clinic model, plus the balance helpers.
    objects = ClinicManager.from_queryset(InstallmentQuerySet)()
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        db_table = "finance_installment"
        verbose_name = _("parcela")
        verbose_name_plural = _("parcelas")
        ordering = ["due_date", "number"]
        indexes = [models.Index(fields=["clinic", "due_date"], name="installment_clinic_due_date")]
        constraints = [
            models.UniqueConstraint(fields=["entry", "number"], name="installment_number_unique"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="installment_amount_positive"),
        ]

    def __str__(self):
        return f"{self.entry.description} {self.number}/{self.entry.installments.count()}"

    def paid_and_balance(self):
        """(principal paid, balance) computed from the payments (not annotated)."""
        pago = sum((p.principal for p in self.payments.all() if not p.reversed), start=ZERO)
        return pago, self.amount - pago


class Payment(ClinicModel):
    """Money received (or paid) for an installment. Partial payments are allowed.

    `valor` is what changed hands; `juros` (late fee, typed by hand) is included in it and
    `desconto` (administrators only) reduces what is owed: the installment is reduced by
    valor - juros + desconto.
    """

    class Method(models.TextChoices):
        """Every method of every country; each country offers some (payment_methods.py, decision
        123)."""

        CASH = "dinheiro", _("Dinheiro")
        PIX = "pix", _("Pix")
        DEBIT = "debito", _("Cartão de débito")
        CREDIT = "credito", _("Cartão de crédito")
        TRANSFER = "transferencia", _("Transferência")
        BOLETO = "boleto", _("Boleto")
        # No longer offered in Brazil (the owner: cheques are not used anymore); kept so
        # payments recorded as cheque there still show their method.
        CHEQUE = "cheque", _("Cheque")
        WALLET = "carteira", _("Carteira digital")
        DIRECT_DEBIT = "debito_auto", _("Débito automático")
        HSA = "hsa", _("Cartão HSA/FSA")
        FINANCING = "financiamento", _("Financiamento ao paciente")
        BPAY = "bpay", "BPAY"

        @classmethod
        def in_use(cls, country=None):
            """The methods offered when recording a payment, in the clinic's country."""
            from .payment_methods import in_use

            return in_use(country)

    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("parcela"),
    )
    date = models.DateField(_("data"), default=timezone.localdate)
    amount = models.DecimalField(_("valor recebido"), **MONEY)
    interest = models.DecimalField(
        _("juros e multa"),
        default=ZERO,
        help_text=_("Já incluídos no valor recebido."),
        **MONEY,
    )
    discount = models.DecimalField(_("desconto"), default=ZERO, **MONEY)
    method = models.CharField(_("forma de pagamento"), max_length=15, choices=Method.choices)
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("conta"),
    )
    # Card details only: never the card number.
    card_brand = models.CharField(_("bandeira do cartão"), max_length=30, blank=True)
    card_installments = models.PositiveSmallIntegerField(
        _("parcelas no cartão"), null=True, blank=True
    )
    card_transaction_code = models.CharField(
        _("código da transação (NSU)"), max_length=40, blank=True
    )
    note = models.CharField(_("observação"), max_length=200, blank=True)
    reversed = models.BooleanField(_("estornado"), default=False)
    reversed_at = models.DateTimeField(_("estornado em"), null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estornado por"),
    )
    reversal_reason = models.CharField(_("motivo do estorno"), max_length=200, blank=True)
    # Practitioner commission (0.19.0): the commission that paid this receipt out, and the
    # one that deducted it again after it was reversed.
    commission = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("comissão"),
    )
    commission_reversal = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_payments",
        verbose_name=_("comissão que descontou o estorno"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("recebido por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "finance_payment"
        verbose_name = _("pagamento")
        verbose_name_plural = _("pagamentos")
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(interest__gte=0), name="payment_interest_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(discount__gte=0), name="payment_discount_not_negative"
            ),
        ]

    def __str__(self):
        return f"{self.installment} – {self.amount}"

    def get_method_display(self):
        """The method's name in the clinic's country ("Transferência (SPEI)" in Mexico)."""
        from .payment_methods import label

        return label(self.method)

    @property
    def principal(self):
        return self.amount - self.interest + self.discount


class CashRegister(ClinicModel):
    """A cash drawer session (0.17.0): opened with a counted amount, closed with another.

    While open, payments registered into its account, withdrawals and top-ups make up the
    expected amount; at closing the expected and counted amounts are stored, so later
    reversals do not change a closed session.
    """

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="cash_registers",
        verbose_name=_("conta"),
    )
    opened_at = models.DateTimeField(_("aberto em"), default=timezone.now)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("aberto por"),
    )
    opening_amount = models.DecimalField(_("valor contado na abertura"), **MONEY)
    closed_at = models.DateTimeField(_("fechado em"), null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("fechado por"),
    )
    expected_amount = models.DecimalField(_("valor esperado"), null=True, blank=True, **MONEY)
    counted_amount = models.DecimalField(
        _("valor contado no fechamento"),
        null=True,
        blank=True,
        **MONEY,
    )
    note = models.CharField(_("observação"), max_length=200, blank=True)

    class Meta:
        db_table = "finance_cash_register"
        verbose_name = _("caixa")
        verbose_name_plural = _("caixas")
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(closed_at__isnull=True),
                name="one_open_cash_register_per_account",
            ),
            models.CheckConstraint(
                condition=Q(opening_amount__gte=0), name="cash_register_opening_not_negative"
            ),
        ]

    def __str__(self):
        return f"{self.account} {timezone.localtime(self.opened_at):%d/%m/%Y %H:%M}"

    @property
    def is_open(self):
        return self.closed_at is None

    @property
    def difference(self):
        if self.counted_amount is None or self.expected_amount is None:
            return None
        return self.counted_amount - self.expected_amount


class CashMovement(ClinicModel):
    """Withdrawal from or top-up of an open cash drawer, optionally to/from another account."""

    class Kind(models.TextChoices):
        WITHDRAWAL = "retirada", _("Retirada (sangria)")
        TOP_UP = "reforco", _("Reforço")

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name=_("caixa"),
    )
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    amount = models.DecimalField(_("valor"), **MONEY)
    other_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("outra conta"),
        help_text=_("Para onde vai a retirada ou de onde vem o reforço (vazio: fora do sistema)."),
    )
    reason = models.CharField(_("motivo"), max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "finance_cash_movement"
        verbose_name = _("movimento de caixa")
        verbose_name_plural = _("movimentos de caixa")
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="cash_movement_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount}"


class Commission(ClinicModel):
    """A practitioner commission paid out (0.19.0, decision 053).

    It covers every receipt of the practitioner's receivables up to `ate` not covered
    before, minus the commission of receipts reversed after being paid out. Paying it
    creates a payable; cancelling that payable cancels the commission and frees the receipts.
    """

    practitioner = models.ForeignKey(
        "profissionais.Practitioner",
        on_delete=models.PROTECT,
        related_name="commissions",
        verbose_name=_("profissional"),
    )
    until = models.DateField(_("recebimentos até"))
    percentage = models.DecimalField(_("percentual"), max_digits=5, decimal_places=2)
    received_amount = models.DecimalField(_("valor recebido"), **MONEY)
    reversal_deduction = models.DecimalField(
        _("comissão de estornos descontada"), default=ZERO, **MONEY
    )
    amount = models.DecimalField(_("valor da comissão"), **MONEY)
    entry = models.OneToOneField(
        Entry,
        on_delete=models.PROTECT,
        related_name="commission",
        verbose_name=_("lançamento a pagar"),
    )
    cancelled = models.BooleanField(_("cancelada"), default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "finance_commission"
        verbose_name = _("comissão")
        verbose_name_plural = _("comissões")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="commission_amount_positive"),
        ]

    def __str__(self):
        return f"{self.practitioner} {self.until:%d/%m/%Y}"

    @property
    def gross(self):
        """Commission on the receipts, before deducting reversals."""
        return self.amount + self.reversal_deduction


class Planning(ClinicModel):
    """The year's goal for a group of the chart of accounts (decision 098, legacy Medical
    planejamento_estrategico): how much to receive or spend, compared with what was paid."""

    year = models.PositiveSmallIntegerField(_("ano"))
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("grupo"),
    )
    amount = models.DecimalField(_("meta"), **MONEY)

    class Meta:
        db_table = "finance_planning"
        verbose_name = _("meta do planejamento")
        verbose_name_plural = _("metas do planejamento")
        ordering = ["year", "group"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "year", "group"], name="planning_unique_per_group"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="planning_amount_positive"),
        ]

    def __str__(self):
        return f"{self.year} · {self.group}"


class BookClosing(ClinicModel):
    """Finance closed up to a date (decision 096), so the reports given to the accountant
    do not change: no payment dated on or before it can be recorded or reversed.

    Each row is a closing or a reopening, kept as history; the newest one rules. A
    reopening has an earlier date (or none: everything open) and a reason.
    """

    until = models.DateField(_("fechado até"), null=True, blank=True)
    reason = models.CharField(_("motivo"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "finance_book_closing"
        verbose_name = _("fechamento do financeiro")
        verbose_name_plural = _("fechamentos do financeiro")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.until:%d/%m/%Y}" if self.until else str(_("Aberto"))


class StatementImport(ClinicModel):
    """One OFX file imported into a bank account (0.20.0, decision 054)."""

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="statement_imports",
        verbose_name=_("conta"),
    )
    file = models.CharField(_("arquivo"), max_length=200)
    bank_code = models.CharField(_("código do banco"), max_length=20, blank=True)
    bank_account_number = models.CharField(_("conta no banco"), max_length=40, blank=True)
    start = models.DateField(_("início"), null=True, blank=True)
    end = models.DateField(_("fim"), null=True, blank=True)
    balance = models.DecimalField(_("saldo no banco"), null=True, blank=True, **MONEY)
    balance_date = models.DateField(_("saldo em"), null=True, blank=True)
    new_transactions = models.PositiveIntegerField(_("transações novas"), default=0)
    duplicate_transactions = models.PositiveIntegerField(_("transações já importadas"), default=0)
    unreadable_transactions = models.PositiveIntegerField(
        _("transações ilegíveis"),
        default=0,
        help_text=_("Linhas do arquivo sem data ou valor que dê para ler: não foram importadas."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("importado por"),
    )
    created_at = models.DateTimeField(_("importado em"), auto_now_add=True)

    class Meta:
        db_table = "finance_statement_import"
        verbose_name = _("importação de extrato")
        verbose_name_plural = _("importações de extrato")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account} {self.file}"


class BankTransaction(ClinicModel):
    """A bank statement line, reconciled with a payment or a drawer movement, or ignored."""

    class Status(models.TextChoices):
        PENDING = "pendente", _("Pendente")
        RECONCILED = "conciliada", _("Conciliada")
        IGNORED = "ignorada", _("Ignorada")

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("conta"),
    )
    statement_import = models.ForeignKey(
        StatementImport,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("importação"),
    )
    fitid = models.CharField(_("identificador no banco"), max_length=120)
    date = models.DateField(_("data"))
    amount = models.DecimalField(
        _("valor"),
        help_text=_("Positivo: entrada; negativo: saída."),
        **MONEY,
    )
    description = models.CharField(_("descrição"), max_length=200, blank=True)
    kind = models.CharField(_("tipo no banco"), max_length=20, blank=True)
    status = models.CharField(
        _("situação"),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transaction",
        verbose_name=_("pagamento"),
    )
    cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transaction",
        verbose_name=_("movimento do caixa"),
    )
    reason = models.CharField(_("motivo"), max_length=200, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("conciliado por"),
    )
    reconciled_at = models.DateTimeField(_("conciliado em"), null=True, blank=True)

    class Meta:
        db_table = "finance_bank_transaction"
        verbose_name = _("transação bancária")
        verbose_name_plural = _("transações bancárias")
        ordering = ["date", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "fitid"], name="bank_transaction_unique_per_account"
            ),
            models.CheckConstraint(
                condition=~Q(payment__isnull=False, cash_movement__isnull=False),
                name="bank_transaction_one_link",
            ),
        ]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} {self.amount} {self.description}"

    @property
    def is_incoming(self):
        return self.amount > 0
