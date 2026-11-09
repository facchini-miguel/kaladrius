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
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core import countries
from apps.core.isolation import ClinicManager, ClinicModel, without_isolation
from apps.core.ordering import ALPHABETICAL

ZERO = Decimal("0.00")
MONEY = {"max_digits": 12, "decimal_places": 2}


class FinancialAccount(ClinicModel):
    """Where the money goes: the cash drawer, a bank account, the card machine."""

    class Kind(models.TextChoices):
        CASH = "cash", _("Cash (drawer)")
        BANK = "bank", _("Bank")
        CARD = "card", _("Card machine")

    name = models.CharField(_("name"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices)
    opening_balance = models.DecimalField(
        _("initial balance"),
        default=ZERO,
        help_text=_("How much the account had before the first entry in the system."),
        **MONEY,
    )
    active = models.BooleanField(pgettext_lazy("feminine", "active"), default=True)

    class Meta:
        db_table = "finance_financial_account"
        verbose_name = _("account")
        verbose_name_plural = _("accounts")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="financial_account_unique")
        ]

    def __str__(self):
        return self.name


class FinancialKind(models.TextChoices):
    INCOME = "income", _("Income")
    EXPENSE = "expense", _("Expense")


class AccountGroup(ClinicModel):
    """A node of the chart of accounts (decision 097, legacy Medical grupocontabil):
    groups hold subgroups and categories; entries go to the categories (the leaves)."""

    Kind = FinancialKind

    name = models.CharField(_("name"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("parent group"),
    )
    code = models.PositiveSmallIntegerField(
        _("code"),
        null=True,
        blank=True,
        help_text=_("Position inside the parent group (1, 2, 3…); builds numbers such as 2.1."),
    )
    active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "finance_account_group"
        verbose_name = _("account group")
        verbose_name_plural = _("account groups")
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
        chain, current = [], self.parent
        while current is not None:
            chain.insert(0, current)
            current = current.parent
        return chain

    @property
    def number(self):
        codes = [g.code for g in [*self.ancestors(), self]]
        return ".".join(map(str, codes)) if None not in codes else ""


class Category(ClinicModel):
    """Grouping of income and expenses for the reports."""

    Kind = FinancialKind

    name = models.CharField(_("name"), max_length=60, db_collation=ALPHABETICAL)
    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices)
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categories",
        verbose_name=_("group"),
    )
    active = models.BooleanField(pgettext_lazy("feminine", "active"), default=True)
    # Which default category this is (decision 205), so the code finds the payroll and the
    # commissions categories by it and not by their names, which are in the clinic's
    # language and which the clinic may change. Empty on the categories the clinic adds.
    key = models.CharField(max_length=30, blank=True, editable=False)

    class Meta:
        db_table = "finance_category"
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "kind", "name"], name="category_unique"),
            models.UniqueConstraint(
                fields=["clinic", "key"], condition=~Q(key=""), name="category_key_unique"
            ),
        ]

    def __str__(self):
        return self.name


class CostCenter(ClinicModel):
    """Who in the clinic an entry is for (decision 095): a room, a specialty, the office.

    Optional on every entry, one per entry (no split across centers yet).
    """

    name = models.CharField(_("name"), max_length=60, db_collation=ALPHABETICAL)
    active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "finance_cost_center"
        verbose_name = _("cost center")
        verbose_name_plural = _("cost centers")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="cost_center_unique")
        ]

    def __str__(self):
        return self.name


# Accounts and categories every new clinic starts with (it can add, rename or deactivate),
# written in the language of the clinic's country (decision 205).
DEFAULT_ACCOUNTS = [
    (pgettext_lazy("default account", "Cash"), FinancialAccount.Kind.CASH),
    (pgettext_lazy("default account", "Bank"), FinancialAccount.Kind.BANK),
]
# Category.key of the defaults the code looks for.
PAYROLL = "payroll"
COMMISSIONS = "commissions"
TREATMENT = "treatment"
# (key, name, kind)
DEFAULT_CATEGORIES = [
    (TREATMENT, pgettext_lazy("default category", "Treatment"), Category.Kind.INCOME),
    ("consultation", pgettext_lazy("default category", "Consultation"), Category.Kind.INCOME),
    ("other_income", pgettext_lazy("default category", "Other income"), Category.Kind.INCOME),
    ("rent", pgettext_lazy("default category", "Rent"), Category.Kind.EXPENSE),
    (
        "dental_supplies",
        pgettext_lazy("default category", "Dental supplies"),
        Category.Kind.EXPENSE,
    ),
    (
        "prosthesis_lab",
        pgettext_lazy("default category", "Dental prosthesis laboratory"),
        Category.Kind.EXPENSE,
    ),
    (
        PAYROLL,
        pgettext_lazy("default category", "Salaries and payroll taxes"),
        Category.Kind.EXPENSE,
    ),
    (COMMISSIONS, pgettext_lazy("default category", "Commissions"), Category.Kind.EXPENSE),
    ("taxes", pgettext_lazy("default category", "Taxes"), Category.Kind.EXPENSE),
    (
        "utilities",
        pgettext_lazy("default category", "Water, electricity and internet"),
        Category.Kind.EXPENSE,
    ),
    ("maintenance", pgettext_lazy("default category", "Maintenance"), Category.Kind.EXPENSE),
    ("other_expenses", pgettext_lazy("default category", "Other expenses"), Category.Kind.EXPENSE),
]
# A basic chart of accounts for new clinics (decision 097): code, group and the keys of its
# categories.
DEFAULT_CHART = {
    Category.Kind.INCOME: [
        (1, pgettext_lazy("default account group", "Appointments"), [TREATMENT, "consultation"]),
        (2, pgettext_lazy("default account group", "Other income"), ["other_income"]),
    ],
    Category.Kind.EXPENSE: [
        (
            1,
            pgettext_lazy("default account group", "Premises"),
            ["rent", "utilities", "maintenance"],
        ),
        (2, pgettext_lazy("default account group", "Personnel"), [PAYROLL, COMMISSIONS]),
        (
            3,
            pgettext_lazy("default account group", "Supplies and laboratory"),
            ["dental_supplies", "prosthesis_lab"],
        ),
        (4, pgettext_lazy("default account group", "Taxes"), ["taxes"]),
        (5, pgettext_lazy("default account group", "Other expenses"), ["other_expenses"]),
    ],
}


def create_defaults(clinic):
    """Default accounts and categories for a clinic that has none, in the language of its
    country: Portuguese in Brazil, Spanish in Latin America, English in the others."""
    language = countries.by_code(clinic.country).language
    with without_isolation(), translation.override(language):
        if not FinancialAccount.objects.filter(clinic=clinic).exists():
            FinancialAccount.objects.bulk_create(
                FinancialAccount(clinic=clinic, name=str(name), kind=kind)
                for name, kind in DEFAULT_ACCOUNTS
            )
        if not Category.objects.filter(clinic=clinic).exists():
            group_of = {}
            for kind, rows in DEFAULT_CHART.items():
                for code, name, keys in rows:
                    group = AccountGroup.objects.create(
                        clinic=clinic, kind=kind, code=code, name=str(name)
                    )
                    group_of.update(dict.fromkeys(keys, group))
            Category.objects.bulk_create(
                Category(clinic=clinic, key=key, name=str(name), kind=kind, group=group_of[key])
                for key, name, kind in DEFAULT_CATEGORIES
            )


class Supplier(ClinicModel):
    """Who the clinic buys from or pays (decision 093), picked on a payable."""

    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", _("Individual")
        COMPANY = "company", _("Company")

    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices, default=Kind.COMPANY)
    name = models.CharField(
        _("name"),
        max_length=200,
        help_text=_("For companies, the trade name."),
        db_collation=ALPHABETICAL,
    )
    legal_name = models.CharField(_("company name"), max_length=200, blank=True)
    # The country's tax document (decision 121); the name stayed from Brazil.
    tax_id = models.CharField(_("document"), max_length=20, blank=True)
    phone = models.CharField(_("phone"), max_length=11, blank=True)
    whatsapp = models.CharField(_("WhatsApp"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    notes = models.TextField(_("notes"), blank=True)
    active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "finance_supplier"
        verbose_name = _("supplier")
        verbose_name_plural = _("suppliers")
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
        return "company" if self.kind == self.Kind.COMPANY else "person"


class Entry(ClinicModel):
    """An amount owed to the clinic (receivable) or by it (payable), in installments."""

    class Kind(models.TextChoices):
        RECEIVABLE = "receivable", _("Receivables")
        PAYABLE = "payable", _("Payables")

    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices)
    description = models.CharField(_("description"), max_length=200)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("category"),
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("cost center"),
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("patient"),
    )
    # Who pays (receivable without a registered patient) or the supplier (payable). With a
    # registered supplier it holds the supplier's name, so lists and reports need no join.
    payer = models.CharField(_("payer"), max_length=200, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        verbose_name=_("supplier"),
    )
    practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("practitioner"),
        help_text=_("Who saw the patient (optional)."),
    )
    total_amount = models.DecimalField(_("total amount"), **MONEY)
    date = models.DateField(_("date"), default=timezone.localdate)
    notes = models.TextField(_("notes"), blank=True)
    cancelled = models.BooleanField(_("cancelled"), default=False)
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cancelled by"),
    )
    cancellation_reason = models.CharField(_("cancellation reason"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "finance_entry"
        verbose_name = _("entry")
        verbose_name_plural = _("entries")
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
        paid = Coalesce(
            Sum(principal, filter=Q(payments__reversed=False)),
            Value(ZERO),
            output_field=DecimalField(**MONEY),
        )
        return self.annotate(paid=paid).annotate(
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
        verbose_name=_("entry"),
    )
    number = models.PositiveSmallIntegerField(_("number"))
    due_date = models.DateField(_("due date"))
    amount = models.DecimalField(_("amount"), **MONEY)

    # Same isolation as every clinic model, plus the balance helpers.
    objects = ClinicManager.from_queryset(InstallmentQuerySet)()
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        db_table = "finance_installment"
        verbose_name = _("installment")
        verbose_name_plural = _("installments")
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
        paid = sum((p.principal for p in self.payments.all() if not p.reversed), start=ZERO)
        return paid, self.amount - paid


class Payment(ClinicModel):
    """Money received (or paid) for an installment. Partial payments are allowed.

    `valor` is what changed hands; `juros` (late fee, typed by hand) is included in it and
    `desconto` (administrators only) reduces what is owed: the installment is reduced by
    valor - juros + desconto.
    """

    class Method(models.TextChoices):
        """Every method of every country; each country offers some (payment_methods.py, decision
        123)."""

        CASH = "cash", _("Cash")
        PIX = "pix", _("Pix")
        DEBIT = "debit", _("Debit card")
        CREDIT = "credit", _("Credit card")
        TRANSFER = "transfer", _("Bank transfer")
        BOLETO = "boleto", _("Boleto (bank slip)")
        # No longer offered in Brazil (the owner: cheques are not used anymore); kept so
        # payments recorded as cheque there still show their method.
        CHEQUE = "cheque", _("Check")
        WALLET = "wallet", _("Digital wallet")
        DIRECT_DEBIT = "direct_debit", _("Direct debit")
        HSA = "hsa", _("HSA/FSA card")
        FINANCING = "financing", _("Patient financing")
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
        verbose_name=_("installment"),
    )
    date = models.DateField(_("date"), default=timezone.localdate)
    amount = models.DecimalField(_("amount received"), **MONEY)
    interest = models.DecimalField(
        _("interest and late fee"),
        default=ZERO,
        help_text=_("Already included in the amount received."),
        **MONEY,
    )
    discount = models.DecimalField(_("discount"), default=ZERO, **MONEY)
    method = models.CharField(_("payment method"), max_length=15, choices=Method.choices)
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("account"),
    )
    # Card details only: never the card number.
    card_brand = models.CharField(_("card brand"), max_length=30, blank=True)
    card_installments = models.PositiveSmallIntegerField(
        _("card installments"), null=True, blank=True
    )
    card_transaction_code = models.CharField(_("transaction code (NSU)"), max_length=40, blank=True)
    note = models.CharField(_("note"), max_length=200, blank=True)
    reversed = models.BooleanField(_("reversed"), default=False)
    reversed_at = models.DateTimeField(_("reversed at"), null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("reversed by"),
    )
    reversal_reason = models.CharField(_("reversal reason"), max_length=200, blank=True)
    # Practitioner commission (0.19.0): the commission that paid this receipt out, and the
    # one that deducted it again after it was reversed.
    commission = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name=_("commission"),
    )
    commission_reversal = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_payments",
        verbose_name=_("commission that deducted the reversal"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("received by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "finance_payment"
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
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
        verbose_name=_("account"),
    )
    opened_at = models.DateTimeField(_("opened at"), default=timezone.now)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("opened by"),
    )
    opening_amount = models.DecimalField(_("amount counted at opening"), **MONEY)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("closed by"),
    )
    expected_amount = models.DecimalField(_("expected amount"), null=True, blank=True, **MONEY)
    counted_amount = models.DecimalField(
        _("amount counted at closing"),
        null=True,
        blank=True,
        **MONEY,
    )
    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        db_table = "finance_cash_register"
        verbose_name = _("cash drawer")
        verbose_name_plural = _("cash drawers")
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
        WITHDRAWAL = "withdrawal", _("Withdrawal")
        TOP_UP = "top_up", _("Top-up")

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name=_("cash drawer"),
    )
    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices)
    amount = models.DecimalField(_("amount"), **MONEY)
    other_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("other account"),
        help_text=_(
            "Where the withdrawal goes or the top-up comes from (empty: outside the system)."
        ),
    )
    reason = models.CharField(_("reason"), max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "finance_cash_movement"
        verbose_name = _("drawer movement")
        verbose_name_plural = _("drawer movements")
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
        "practitioners.Practitioner",
        on_delete=models.PROTECT,
        related_name="commissions",
        verbose_name=_("practitioner"),
    )
    until = models.DateField(_("receipts up to"))
    percentage = models.DecimalField(_("percentage"), max_digits=5, decimal_places=2)
    received_amount = models.DecimalField(_("amount received"), **MONEY)
    reversal_deduction = models.DecimalField(
        _("commission of reversals deducted"), default=ZERO, **MONEY
    )
    amount = models.DecimalField(_("commission amount"), **MONEY)
    entry = models.OneToOneField(
        Entry,
        on_delete=models.PROTECT,
        related_name="commission",
        verbose_name=_("payable"),
    )
    cancelled = models.BooleanField(pgettext_lazy("feminine", "cancelled"), default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "finance_commission"
        verbose_name = _("commission")
        verbose_name_plural = _("commissions")
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

    year = models.PositiveSmallIntegerField(_("year"))
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("group"),
    )
    amount = models.DecimalField(_("goal"), **MONEY)

    class Meta:
        db_table = "finance_planning"
        verbose_name = _("planning goal")
        verbose_name_plural = _("planning goals")
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

    until = models.DateField(_("closed up to"), null=True, blank=True)
    reason = models.CharField(_("reason"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "finance_book_closing"
        verbose_name = _("finance closing")
        verbose_name_plural = _("finance closings")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.until:%d/%m/%Y}" if self.until else str(_("Open"))


class StatementImport(ClinicModel):
    """One OFX file imported into a bank account (0.20.0, decision 054)."""

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="statement_imports",
        verbose_name=_("account"),
    )
    file = models.CharField(_("file"), max_length=200)
    bank_code = models.CharField(_("bank code"), max_length=20, blank=True)
    bank_account_number = models.CharField(_("bank account"), max_length=40, blank=True)
    start = models.DateField(_("start"), null=True, blank=True)
    end = models.DateField(_("end"), null=True, blank=True)
    balance = models.DecimalField(_("bank balance"), null=True, blank=True, **MONEY)
    balance_date = models.DateField(_("balance on"), null=True, blank=True)
    new_transactions = models.PositiveIntegerField(_("new transactions"), default=0)
    duplicate_transactions = models.PositiveIntegerField(
        _("transactions already imported"), default=0
    )
    unreadable_transactions = models.PositiveIntegerField(
        _("unreadable transactions"),
        default=0,
        help_text=_("Lines of the file without a readable date or amount: they were not imported."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("imported by"),
    )
    created_at = models.DateTimeField(_("imported at"), auto_now_add=True)

    class Meta:
        db_table = "finance_statement_import"
        verbose_name = _("statement import")
        verbose_name_plural = _("statement imports")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account} {self.file}"


class BankTransaction(ClinicModel):
    """A bank statement line, reconciled with a payment or a drawer movement, or ignored."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RECONCILED = "reconciled", _("Reconciled")
        IGNORED = "ignored", _("Ignored")

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("account"),
    )
    statement_import = models.ForeignKey(
        StatementImport,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("import"),
    )
    fitid = models.CharField(_("bank identifier"), max_length=120)
    date = models.DateField(_("date"))
    amount = models.DecimalField(
        _("amount"),
        help_text=_("Positive: money in; negative: money out."),
        **MONEY,
    )
    description = models.CharField(_("description"), max_length=200, blank=True)
    kind = models.CharField(_("bank type"), max_length=20, blank=True)
    status = models.CharField(
        _("status"),
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
        verbose_name=_("payment"),
    )
    cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transaction",
        verbose_name=pgettext_lazy("of the drawer", "drawer movement"),
    )
    reason = models.CharField(_("reason"), max_length=200, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("reconciled by"),
    )
    reconciled_at = models.DateTimeField(_("reconciled at"), null=True, blank=True)

    class Meta:
        db_table = "finance_bank_transaction"
        verbose_name = _("bank transaction")
        verbose_name_plural = _("bank transactions")
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
