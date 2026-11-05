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

from apps.core.isolation import ClinicaManager, ModeloDaClinica, sem_isolamento
from apps.core.ordering import ALFABETICA

ZERO = Decimal("0.00")
DINHEIRO = {"max_digits": 12, "decimal_places": 2}


class FinancialAccount(ModeloDaClinica):
    """Where the money goes: the cash drawer, a bank account, the card machine."""

    class Tipo(models.TextChoices):
        DINHEIRO = "dinheiro", _("Dinheiro (caixa)")
        BANCO = "banco", _("Banco")
        CARTAO = "cartao", _("Maquininha de cartão")

    name = models.CharField(_("nome"), max_length=60, db_collation=ALFABETICA, db_column="nome")
    kind = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices, db_column="tipo")
    opening_balance = models.DecimalField(
        _("saldo inicial"),
        default=ZERO,
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
        **DINHEIRO,
        db_column="saldo_inicial",
    )
    active = models.BooleanField(_("ativa"), default=True, db_column="ativa")

    class Meta:
        db_table = "financeiro_conta"
        verbose_name = _("conta")
        verbose_name_plural = _("contas")
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["clinic", "name"], name="conta_unica")]

    def __str__(self):
        return self.name


class TipoFinanceiro(models.TextChoices):
    RECEITA = "receita", _("Receita")
    DESPESA = "despesa", _("Despesa")


class AccountGroup(ModeloDaClinica):
    """A node of the chart of accounts (decision 097, legacy Medical grupocontabil):
    groups hold subgroups and categories; entries go to the categories (the leaves)."""

    Tipo = TipoFinanceiro

    name = models.CharField(_("nome"), max_length=60, db_collation=ALFABETICA, db_column="nome")
    kind = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices, db_column="tipo")
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="filhos",
        verbose_name=_("grupo acima"),
        db_column="pai_id",
    )
    code = models.PositiveSmallIntegerField(
        _("código"),
        null=True,
        blank=True,
        help_text=_("Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1."),
        db_column="codigo",
    )
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")

    class Meta:
        db_table = "financeiro_grupocontabil"
        verbose_name = _("grupo contábil")
        verbose_name_plural = _("grupos contábeis")
        ordering = ["kind", "code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "kind", "parent", "name"], name="grupo_contabil_unico"
            )
        ]

    def __str__(self):
        return f"{self.number} {self.name}" if self.number else self.name

    def ancestrais(self):
        """From the top group down to the parent of this one."""
        cadeia, atual = [], self.parent
        while atual is not None:
            cadeia.insert(0, atual)
            atual = atual.parent
        return cadeia

    @property
    def number(self):
        codigos = [g.code for g in [*self.ancestrais(), self]]
        return ".".join(map(str, codigos)) if None not in codigos else ""


class Category(ModeloDaClinica):
    """Grouping of income and expenses for the reports."""

    Tipo = TipoFinanceiro

    name = models.CharField(_("nome"), max_length=60, db_collation=ALFABETICA, db_column="nome")
    kind = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices, db_column="tipo")
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categorias",
        verbose_name=_("grupo"),
        db_column="grupo_id",
    )
    active = models.BooleanField(_("ativa"), default=True, db_column="ativa")

    class Meta:
        db_table = "financeiro_categoria"
        verbose_name = _("categoria")
        verbose_name_plural = _("categorias")
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "kind", "name"], name="categoria_unica")
        ]

    def __str__(self):
        return self.name


class CostCenter(ModeloDaClinica):
    """Who in the clinic an entry is for (decision 095): a room, a specialty, the office.

    Optional on every entry, one per entry (no split across centers yet).
    """

    name = models.CharField(_("nome"), max_length=60, db_collation=ALFABETICA, db_column="nome")
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")

    class Meta:
        db_table = "financeiro_centrocusto"
        verbose_name = _("centro de custo")
        verbose_name_plural = _("centros de custo")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="centro_custo_unico")
        ]

    def __str__(self):
        return self.name


# Accounts and categories every new clinic starts with (it can add, rename or deactivate).
CONTAS_PADRAO = [("Caixa", FinancialAccount.Tipo.DINHEIRO), ("Banco", FinancialAccount.Tipo.BANCO)]
CATEGORIAS_PADRAO = [
    ("Tratamento", Category.Tipo.RECEITA),
    ("Consulta", Category.Tipo.RECEITA),
    ("Outras receitas", Category.Tipo.RECEITA),
    ("Aluguel", Category.Tipo.DESPESA),
    ("Material odontológico", Category.Tipo.DESPESA),
    ("Laboratório de prótese", Category.Tipo.DESPESA),
    ("Salários e encargos", Category.Tipo.DESPESA),
    ("Comissões", Category.Tipo.DESPESA),
    ("Impostos", Category.Tipo.DESPESA),
    ("Água, luz e internet", Category.Tipo.DESPESA),
    ("Manutenção", Category.Tipo.DESPESA),
    ("Outras despesas", Category.Tipo.DESPESA),
]
# A basic chart of accounts for new clinics (decision 097): code, group and its categories.
PLANO_PADRAO = {
    Category.Tipo.RECEITA: [
        (1, "Atendimentos", ["Tratamento", "Consulta"]),
        (2, "Outras receitas", ["Outras receitas"]),
    ],
    Category.Tipo.DESPESA: [
        (1, "Ocupação", ["Aluguel", "Água, luz e internet", "Manutenção"]),
        (2, "Pessoal", ["Salários e encargos", "Comissões"]),
        (3, "Materiais e laboratório", ["Material odontológico", "Laboratório de prótese"]),
        (4, "Impostos", ["Impostos"]),
        (5, "Outras despesas", ["Outras despesas"]),
    ],
}


def criar_padroes(clinic):
    """Default accounts and categories for a clinic that has none."""
    with sem_isolamento():
        if not FinancialAccount.objects.filter(clinic=clinic).exists():
            FinancialAccount.objects.bulk_create(
                FinancialAccount(clinic=clinic, name=name, kind=kind)
                for name, kind in CONTAS_PADRAO
            )
        if not Category.objects.filter(clinic=clinic).exists():
            grupo_de = {}
            for kind, linhas in PLANO_PADRAO.items():
                for code, name, categorias in linhas:
                    group = AccountGroup.objects.create(
                        clinic=clinic, kind=kind, code=code, name=name
                    )
                    grupo_de.update({(kind, category): group for category in categorias})
            Category.objects.bulk_create(
                Category(clinic=clinic, name=name, kind=kind, group=grupo_de.get((kind, name)))
                for name, kind in CATEGORIAS_PADRAO
            )


class Supplier(ModeloDaClinica):
    """Who the clinic buys from or pays (decision 093), picked on a payable."""

    class Tipo(models.TextChoices):
        FISICA = "PF", _("Pessoa física")
        JURIDICA = "PJ", _("Pessoa jurídica")

    kind = models.CharField(
        _("tipo"), max_length=2, choices=Tipo.choices, default=Tipo.JURIDICA, db_column="tipo"
    )
    name = models.CharField(
        _("nome"),
        max_length=200,
        help_text=_("Para pessoa jurídica, o nome fantasia."),
        db_collation=ALFABETICA,
        db_column="nome",
    )
    legal_name = models.CharField(
        _("razão social"), max_length=200, blank=True, db_column="razao_social"
    )
    # The country's tax document (decision 121); the name stayed from Brazil.
    tax_id = models.CharField(_("documento"), max_length=20, blank=True, db_column="cpf_cnpj")
    phone = models.CharField(_("telefone"), max_length=11, blank=True, db_column="telefone")
    whatsapp = models.CharField(_("WhatsApp"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    notes = models.TextField(_("observações"), blank=True, db_column="observacoes")
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "financeiro_fornecedor"
        verbose_name = _("fornecedor")
        verbose_name_plural = _("fornecedores")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "tax_id"],
                condition=~Q(tax_id=""),
                name="fornecedor_cpf_cnpj_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def papel_documento(self):
        """Its document's role in apps/core/identification.py."""
        return "empresa" if self.kind == self.Tipo.JURIDICA else "pessoa"


class Entry(ModeloDaClinica):
    """An amount owed to the clinic (receivable) or by it (payable), in installments."""

    class Tipo(models.TextChoices):
        RECEBER = "receber", _("A receber")
        PAGAR = "pagar", _("A pagar")

    kind = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices, db_column="tipo")
    description = models.CharField(_("descrição"), max_length=200, db_column="descricao")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("categoria"),
        db_column="categoria_id",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("centro de custo"),
        db_column="centro_custo_id",
    )
    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("paciente"),
        db_column="paciente_id",
    )
    # Who pays (receivable without a registered patient) or the supplier (payable). With a
    # registered supplier it holds the supplier's name, so lists and reports need no join.
    payer = models.CharField(_("pagador"), max_length=200, blank=True, db_column="pessoa")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("fornecedor"),
        db_column="fornecedor_id",
    )
    practitioner = models.ForeignKey(
        "profissionais.Practitioner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("profissional"),
        help_text=_("Quem fez o atendimento (opcional)."),
        db_column="profissional_id",
    )
    total_amount = models.DecimalField(_("valor total"), **DINHEIRO, db_column="valor_total")
    date = models.DateField(_("data"), default=timezone.localdate, db_column="data")
    notes = models.TextField(_("observações"), blank=True, db_column="observacoes")
    cancelled = models.BooleanField(_("cancelado"), default=False, db_column="cancelado")
    cancelled_at = models.DateTimeField(
        _("cancelado em"), null=True, blank=True, db_column="cancelado_em"
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cancelado por"),
        db_column="cancelado_por_id",
    )
    cancellation_reason = models.CharField(
        _("motivo do cancelamento"), max_length=200, blank=True, db_column="motivo_cancelamento"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "financeiro_lancamento"
        verbose_name = _("lançamento")
        verbose_name_plural = _("lançamentos")
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount__gt=0), name="lancamento_valor_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.description} ({self.nome_pessoa})"

    @property
    def nome_pessoa(self):
        return self.patient.name if self.patient_id else self.payer


class ParcelaQuerySet(models.QuerySet):
    def com_saldo(self):
        """Annotate pago (principal paid by non-reversed payments) and saldo."""
        principal = ExpressionWrapper(
            F("pagamentos__amount") - F("pagamentos__interest") + F("pagamentos__discount"),
            output_field=DecimalField(**DINHEIRO),
        )
        pago = Coalesce(
            Sum(principal, filter=Q(pagamentos__reversed=False)),
            Value(ZERO),
            output_field=DecimalField(**DINHEIRO),
        )
        return self.annotate(pago=pago).annotate(
            balance=ExpressionWrapper(
                F("amount") - F("pago"), output_field=DecimalField(**DINHEIRO)
            )
        )

    def abertas(self):
        """Installments still owed (positive balance) of entries not cancelled."""
        return self.com_saldo().filter(balance__gt=0, entry__cancelled=False)


class Installment(ModeloDaClinica):
    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name="parcelas",
        verbose_name=_("lançamento"),
        db_column="lancamento_id",
    )
    number = models.PositiveSmallIntegerField(_("número"), db_column="numero")
    due_date = models.DateField(_("vencimento"), db_column="vencimento")
    amount = models.DecimalField(_("valor"), **DINHEIRO, db_column="valor")

    # Same isolation as every clinic model, plus the balance helpers.
    objects = ClinicaManager.from_queryset(ParcelaQuerySet)()
    todos = models.Manager()  # noqa: DJ012

    class Meta:
        db_table = "financeiro_parcela"
        verbose_name = _("parcela")
        verbose_name_plural = _("parcelas")
        ordering = ["due_date", "number"]
        indexes = [models.Index(fields=["clinic", "due_date"], name="parcela_clinica_vencimento")]
        constraints = [
            models.UniqueConstraint(fields=["entry", "number"], name="parcela_numero_unico"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="parcela_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.entry.description} {self.number}/{self.entry.parcelas.count()}"

    def valores(self):
        """(principal paid, balance) computed from the payments (not annotated)."""
        pago = sum((p.principal for p in self.pagamentos.all() if not p.reversed), start=ZERO)
        return pago, self.amount - pago


class Payment(ModeloDaClinica):
    """Money received (or paid) for an installment. Partial payments are allowed.

    `valor` is what changed hands; `juros` (late fee, typed by hand) is included in it and
    `desconto` (administrators only) reduces what is owed: the installment is reduced by
    valor - juros + desconto.
    """

    class Forma(models.TextChoices):
        """Every method of every country; each country offers some (payment_methods.py, decision
        123)."""

        DINHEIRO = "dinheiro", _("Dinheiro")
        PIX = "pix", _("Pix")
        DEBITO = "debito", _("Cartão de débito")
        CREDITO = "credito", _("Cartão de crédito")
        TRANSFERENCIA = "transferencia", _("Transferência")
        BOLETO = "boleto", _("Boleto")
        # No longer offered in Brazil (the owner: cheques are not used anymore); kept so
        # payments recorded as cheque there still show their method.
        CHEQUE = "cheque", _("Cheque")
        CARTEIRA = "carteira", _("Carteira digital")
        DEBITO_AUTOMATICO = "debito_auto", _("Débito automático")
        HSA = "hsa", _("Cartão HSA/FSA")
        FINANCIAMENTO = "financiamento", _("Financiamento ao paciente")
        BPAY = "bpay", "BPAY"

        @classmethod
        def em_uso(cls, country=None):
            """The methods offered when recording a payment, in the clinic's country."""
            from .payment_methods import em_uso

            return em_uso(country)

    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        related_name="pagamentos",
        verbose_name=_("parcela"),
        db_column="parcela_id",
    )
    date = models.DateField(_("data"), default=timezone.localdate, db_column="data")
    amount = models.DecimalField(_("valor recebido"), **DINHEIRO, db_column="valor")
    interest = models.DecimalField(
        _("juros e multa"),
        default=ZERO,
        help_text=_("Já incluídos no valor recebido."),
        **DINHEIRO,
        db_column="juros",
    )
    discount = models.DecimalField(_("desconto"), default=ZERO, **DINHEIRO, db_column="desconto")
    method = models.CharField(
        _("forma de pagamento"), max_length=15, choices=Forma.choices, db_column="forma"
    )
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("conta"),
        db_column="conta_id",
    )
    # Card details only: never the card number.
    card_brand = models.CharField(
        _("bandeira do cartão"), max_length=30, blank=True, db_column="cartao_bandeira"
    )
    card_installments = models.PositiveSmallIntegerField(
        _("parcelas no cartão"), null=True, blank=True, db_column="cartao_parcelas"
    )
    card_transaction_code = models.CharField(
        _("código da transação (NSU)"), max_length=40, blank=True, db_column="cartao_codigo"
    )
    note = models.CharField(_("observação"), max_length=200, blank=True, db_column="observacao")
    reversed = models.BooleanField(_("estornado"), default=False, db_column="estornado")
    reversed_at = models.DateTimeField(
        _("estornado em"), null=True, blank=True, db_column="estornado_em"
    )
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estornado por"),
        db_column="estornado_por_id",
    )
    reversal_reason = models.CharField(
        _("motivo do estorno"), max_length=200, blank=True, db_column="motivo_estorno"
    )
    # Practitioner commission (0.19.0): the commission that paid this receipt out, and the
    # one that deducted it again after it was reversed.
    commission = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos",
        verbose_name=_("comissão"),
        db_column="comissao_id",
    )
    commission_reversal = models.ForeignKey(
        "Commission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos_estornados",
        verbose_name=_("comissão que descontou o estorno"),
        db_column="comissao_estorno_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("recebido por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "financeiro_pagamento"
        verbose_name = _("pagamento")
        verbose_name_plural = _("pagamentos")
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="pagamento_valor_positivo"),
            models.CheckConstraint(condition=Q(interest__gte=0), name="pagamento_juros_positivo"),
            models.CheckConstraint(
                condition=Q(discount__gte=0), name="pagamento_desconto_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.installment} – {self.amount}"

    def get_method_display(self):
        """The method's name in the clinic's country ("Transferência (SPEI)" in Mexico)."""
        from .payment_methods import rotulo

        return rotulo(self.method)

    @property
    def principal(self):
        return self.amount - self.interest + self.discount


class CashRegister(ModeloDaClinica):
    """A cash drawer session (0.17.0): opened with a counted amount, closed with another.

    While open, payments registered into its account, withdrawals and top-ups make up the
    expected amount; at closing the expected and counted amounts are stored, so later
    reversals do not change a closed session.
    """

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="caixas",
        verbose_name=_("conta"),
        db_column="conta_id",
    )
    opened_at = models.DateTimeField(_("aberto em"), default=timezone.now, db_column="aberto_em")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("aberto por"),
        db_column="aberto_por_id",
    )
    opening_amount = models.DecimalField(
        _("valor contado na abertura"), **DINHEIRO, db_column="valor_abertura"
    )
    closed_at = models.DateTimeField(_("fechado em"), null=True, blank=True, db_column="fechado_em")
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("fechado por"),
        db_column="fechado_por_id",
    )
    expected_amount = models.DecimalField(
        _("valor esperado"), null=True, blank=True, **DINHEIRO, db_column="valor_esperado"
    )
    counted_amount = models.DecimalField(
        _("valor contado no fechamento"),
        null=True,
        blank=True,
        **DINHEIRO,
        db_column="valor_contado",
    )
    note = models.CharField(_("observação"), max_length=200, blank=True, db_column="observacao")

    class Meta:
        db_table = "financeiro_caixa"
        verbose_name = _("caixa")
        verbose_name_plural = _("caixas")
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(closed_at__isnull=True),
                name="um_caixa_aberto_por_conta",
            ),
            models.CheckConstraint(
                condition=Q(opening_amount__gte=0), name="caixa_abertura_positiva"
            ),
        ]

    def __str__(self):
        return f"{self.account} {timezone.localtime(self.opened_at):%d/%m/%Y %H:%M}"

    @property
    def aberto(self):
        return self.closed_at is None

    @property
    def diferenca(self):
        if self.counted_amount is None or self.expected_amount is None:
            return None
        return self.counted_amount - self.expected_amount


class CashMovement(ModeloDaClinica):
    """Withdrawal from or top-up of an open cash drawer, optionally to/from another account."""

    class Tipo(models.TextChoices):
        RETIRADA = "retirada", _("Retirada (sangria)")
        REFORCO = "reforco", _("Reforço")

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="movimentos",
        verbose_name=_("caixa"),
        db_column="caixa_id",
    )
    kind = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices, db_column="tipo")
    amount = models.DecimalField(_("valor"), **DINHEIRO, db_column="valor")
    other_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("outra conta"),
        help_text=_("Para onde vai a retirada ou de onde vem o reforço (vazio: fora do sistema)."),
        db_column="outra_conta_id",
    )
    reason = models.CharField(_("motivo"), max_length=200, db_column="motivo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "financeiro_movimentocaixa"
        verbose_name = _("movimento de caixa")
        verbose_name_plural = _("movimentos de caixa")
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="movimento_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount}"


class Commission(ModeloDaClinica):
    """A practitioner commission paid out (0.19.0, decision 053).

    It covers every receipt of the practitioner's receivables up to `ate` not covered
    before, minus the commission of receipts reversed after being paid out. Paying it
    creates a payable; cancelling that payable cancels the commission and frees the receipts.
    """

    practitioner = models.ForeignKey(
        "profissionais.Practitioner",
        on_delete=models.PROTECT,
        related_name="comissoes",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    until = models.DateField(_("recebimentos até"), db_column="ate")
    percentage = models.DecimalField(
        _("percentual"), max_digits=5, decimal_places=2, db_column="percentual"
    )
    received_amount = models.DecimalField(_("valor recebido"), **DINHEIRO, db_column="recebido")
    reversal_deduction = models.DecimalField(
        _("comissão de estornos descontada"), default=ZERO, **DINHEIRO, db_column="estornos"
    )
    amount = models.DecimalField(_("valor da comissão"), **DINHEIRO, db_column="valor")
    entry = models.OneToOneField(
        Entry,
        on_delete=models.PROTECT,
        related_name="commission",
        verbose_name=_("lançamento a pagar"),
        db_column="lancamento_id",
    )
    cancelled = models.BooleanField(_("cancelada"), default=False, db_column="cancelada")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "financeiro_comissao"
        verbose_name = _("comissão")
        verbose_name_plural = _("comissões")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="comissao_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.practitioner} {self.until:%d/%m/%Y}"

    @property
    def bruta(self):
        """Commission on the receipts, before deducting reversals."""
        return self.amount + self.reversal_deduction


class Planning(ModeloDaClinica):
    """The year's goal for a group of the chart of accounts (decision 098, legacy Medical
    planejamento_estrategico): how much to receive or spend, compared with what was paid."""

    year = models.PositiveSmallIntegerField(_("ano"), db_column="ano")
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("grupo"),
        db_column="grupo_id",
    )
    amount = models.DecimalField(_("meta"), **DINHEIRO, db_column="valor")

    class Meta:
        db_table = "financeiro_planejamento"
        verbose_name = _("meta do planejamento")
        verbose_name_plural = _("metas do planejamento")
        ordering = ["year", "group"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "year", "group"], name="planejamento_unico_por_grupo"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="planejamento_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.year} · {self.group}"


class BookClosing(ModeloDaClinica):
    """Finance closed up to a date (decision 096), so the reports given to the accountant
    do not change: no payment dated on or before it can be recorded or reversed.

    Each row is a closing or a reopening, kept as history; the newest one rules. A
    reopening has an earlier date (or none: everything open) and a reason.
    """

    until = models.DateField(_("fechado até"), null=True, blank=True, db_column="ate")
    reason = models.CharField(_("motivo"), max_length=200, blank=True, db_column="motivo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "financeiro_fechamento"
        verbose_name = _("fechamento do financeiro")
        verbose_name_plural = _("fechamentos do financeiro")
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.until:%d/%m/%Y}" if self.until else str(_("Aberto"))


class StatementImport(ModeloDaClinica):
    """One OFX file imported into a bank account (0.20.0, decision 054)."""

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="importacoes",
        verbose_name=_("conta"),
        db_column="conta_id",
    )
    file = models.CharField(_("arquivo"), max_length=200, db_column="arquivo")
    bank_code = models.CharField(_("código do banco"), max_length=20, blank=True, db_column="banco")
    bank_account_number = models.CharField(
        _("conta no banco"), max_length=40, blank=True, db_column="conta_no_banco"
    )
    start = models.DateField(_("início"), null=True, blank=True, db_column="inicio")
    end = models.DateField(_("fim"), null=True, blank=True, db_column="fim")
    balance = models.DecimalField(
        _("saldo no banco"), null=True, blank=True, **DINHEIRO, db_column="saldo"
    )
    balance_date = models.DateField(_("saldo em"), null=True, blank=True, db_column="saldo_em")
    new_transactions = models.PositiveIntegerField(
        _("transações novas"), default=0, db_column="novas"
    )
    duplicate_transactions = models.PositiveIntegerField(
        _("transações já importadas"), default=0, db_column="repetidas"
    )
    unreadable_transactions = models.PositiveIntegerField(
        _("transações ilegíveis"),
        default=0,
        help_text=_("Linhas do arquivo sem data ou valor que dê para ler: não foram importadas."),
        db_column="ignoradas",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("importado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("importado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "financeiro_importacaoextrato"
        verbose_name = _("importação de extrato")
        verbose_name_plural = _("importações de extrato")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account} {self.file}"


class BankTransaction(ModeloDaClinica):
    """A bank statement line, reconciled with a payment or a drawer movement, or ignored."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", _("Pendente")
        CONCILIADA = "conciliada", _("Conciliada")
        IGNORADA = "ignorada", _("Ignorada")

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="transacoes",
        verbose_name=_("conta"),
        db_column="conta_id",
    )
    statement_import = models.ForeignKey(
        StatementImport,
        on_delete=models.PROTECT,
        related_name="transacoes",
        verbose_name=_("importação"),
        db_column="importacao_id",
    )
    fitid = models.CharField(_("identificador no banco"), max_length=120)
    date = models.DateField(_("data"), db_column="data")
    amount = models.DecimalField(
        _("valor"),
        help_text=_("Positivo: entrada; negativo: saída."),
        **DINHEIRO,
        db_column="valor",
    )
    description = models.CharField(
        _("descrição"), max_length=200, blank=True, db_column="descricao"
    )
    kind = models.CharField(_("tipo no banco"), max_length=20, blank=True, db_column="tipo")
    status = models.CharField(
        _("situação"),
        max_length=10,
        choices=Situacao.choices,
        default=Situacao.PENDENTE,
        db_column="situacao",
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacao",
        verbose_name=_("pagamento"),
        db_column="pagamento_id",
    )
    cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacao",
        verbose_name=_("movimento do caixa"),
        db_column="movimento_id",
    )
    reason = models.CharField(_("motivo"), max_length=200, blank=True, db_column="motivo")
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("conciliado por"),
        db_column="conciliado_por_id",
    )
    reconciled_at = models.DateTimeField(
        _("conciliado em"), null=True, blank=True, db_column="conciliado_em"
    )

    class Meta:
        db_table = "financeiro_transacaobancaria"
        verbose_name = _("transação bancária")
        verbose_name_plural = _("transações bancárias")
        ordering = ["date", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["account", "fitid"], name="transacao_unica_por_conta"),
            models.CheckConstraint(
                condition=~Q(payment__isnull=False, cash_movement__isnull=False),
                name="transacao_um_vinculo",
            ),
        ]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} {self.amount} {self.description}"

    @property
    def entrada(self):
        return self.amount > 0
