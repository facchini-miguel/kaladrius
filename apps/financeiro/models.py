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

from apps.core.isolamento import ClinicaManager, ModeloDaClinica, sem_isolamento

ZERO = Decimal("0.00")
DINHEIRO = {"max_digits": 12, "decimal_places": 2}


class Conta(ModeloDaClinica):
    """Where the money goes: the cash drawer, a bank account, the card machine."""

    class Tipo(models.TextChoices):
        DINHEIRO = "dinheiro", _("Dinheiro (caixa)")
        BANCO = "banco", _("Banco")
        CARTAO = "cartao", _("Maquininha de cartão")

    nome = models.CharField(_("nome"), max_length=60)
    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    saldo_inicial = models.DecimalField(
        _("saldo inicial"),
        default=ZERO,
        help_text=_("Quanto havia na conta antes do primeiro lançamento no sistema."),
        **DINHEIRO,
    )
    ativa = models.BooleanField(_("ativa"), default=True)

    class Meta:
        verbose_name = _("conta")
        verbose_name_plural = _("contas")
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["clinica", "nome"], name="conta_unica")]

    def __str__(self):
        return self.nome


class Categoria(ModeloDaClinica):
    """Grouping of income and expenses for the reports."""

    class Tipo(models.TextChoices):
        RECEITA = "receita", _("Receita")
        DESPESA = "despesa", _("Despesa")

    nome = models.CharField(_("nome"), max_length=60)
    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    ativa = models.BooleanField(_("ativa"), default=True)

    class Meta:
        verbose_name = _("categoria")
        verbose_name_plural = _("categorias")
        ordering = ["tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "tipo", "nome"], name="categoria_unica")
        ]

    def __str__(self):
        return self.nome


# Accounts and categories every new clinic starts with (it can add, rename or deactivate).
CONTAS_PADRAO = [("Caixa", Conta.Tipo.DINHEIRO), ("Banco", Conta.Tipo.BANCO)]
CATEGORIAS_PADRAO = [
    ("Tratamento", Categoria.Tipo.RECEITA),
    ("Consulta", Categoria.Tipo.RECEITA),
    ("Outras receitas", Categoria.Tipo.RECEITA),
    ("Aluguel", Categoria.Tipo.DESPESA),
    ("Material odontológico", Categoria.Tipo.DESPESA),
    ("Laboratório de prótese", Categoria.Tipo.DESPESA),
    ("Salários e encargos", Categoria.Tipo.DESPESA),
    ("Impostos", Categoria.Tipo.DESPESA),
    ("Água, luz e internet", Categoria.Tipo.DESPESA),
    ("Manutenção", Categoria.Tipo.DESPESA),
    ("Outras despesas", Categoria.Tipo.DESPESA),
]


def criar_padroes(clinica):
    """Default accounts and categories for a clinic that has none."""
    with sem_isolamento():
        if not Conta.objects.filter(clinica=clinica).exists():
            Conta.objects.bulk_create(
                Conta(clinica=clinica, nome=nome, tipo=tipo) for nome, tipo in CONTAS_PADRAO
            )
        if not Categoria.objects.filter(clinica=clinica).exists():
            Categoria.objects.bulk_create(
                Categoria(clinica=clinica, nome=nome, tipo=tipo) for nome, tipo in CATEGORIAS_PADRAO
            )


class Lancamento(ModeloDaClinica):
    """An amount owed to the clinic (receivable) or by it (payable), in installments."""

    class Tipo(models.TextChoices):
        RECEBER = "receber", _("A receber")
        PAGAR = "pagar", _("A pagar")

    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    descricao = models.CharField(_("descrição"), max_length=200)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="+", verbose_name=_("categoria")
    )
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("paciente"),
    )
    # Who pays (receivable without a registered patient) or the supplier (payable).
    pessoa = models.CharField(_("pagador"), max_length=200, blank=True)
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("profissional"),
        help_text=_("Quem fez o atendimento (opcional)."),
    )
    valor_total = models.DecimalField(_("valor total"), **DINHEIRO)
    data = models.DateField(_("data"), default=timezone.localdate)
    observacoes = models.TextField(_("observações"), blank=True)
    cancelado = models.BooleanField(_("cancelado"), default=False)
    cancelado_em = models.DateTimeField(_("cancelado em"), null=True, blank=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cancelado por"),
    )
    motivo_cancelamento = models.CharField(_("motivo do cancelamento"), max_length=200, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("lançamento")
        verbose_name_plural = _("lançamentos")
        ordering = ["-data", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_total__gt=0), name="lancamento_valor_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.descricao} ({self.nome_pessoa})"

    @property
    def nome_pessoa(self):
        return self.paciente.nome if self.paciente_id else self.pessoa


class ParcelaQuerySet(models.QuerySet):
    def com_saldo(self):
        """Annotate pago (principal paid by non-reversed payments) and saldo."""
        principal = ExpressionWrapper(
            F("pagamentos__valor") - F("pagamentos__juros") + F("pagamentos__desconto"),
            output_field=DecimalField(**DINHEIRO),
        )
        pago = Coalesce(
            Sum(principal, filter=Q(pagamentos__estornado=False)),
            Value(ZERO),
            output_field=DecimalField(**DINHEIRO),
        )
        return self.annotate(pago=pago).annotate(
            saldo=ExpressionWrapper(F("valor") - F("pago"), output_field=DecimalField(**DINHEIRO))
        )

    def abertas(self):
        """Installments still owed (positive balance) of entries not cancelled."""
        return self.com_saldo().filter(saldo__gt=0, lancamento__cancelado=False)


class Parcela(ModeloDaClinica):
    lancamento = models.ForeignKey(
        Lancamento, on_delete=models.CASCADE, related_name="parcelas", verbose_name=_("lançamento")
    )
    numero = models.PositiveSmallIntegerField(_("número"))
    vencimento = models.DateField(_("vencimento"))
    valor = models.DecimalField(_("valor"), **DINHEIRO)

    # Same isolation as every clinic model, plus the balance helpers.
    objects = ClinicaManager.from_queryset(ParcelaQuerySet)()
    todos = models.Manager()  # noqa: DJ012

    class Meta:
        verbose_name = _("parcela")
        verbose_name_plural = _("parcelas")
        ordering = ["vencimento", "numero"]
        indexes = [
            models.Index(fields=["clinica", "vencimento"], name="parcela_clinica_vencimento")
        ]
        constraints = [
            models.UniqueConstraint(fields=["lancamento", "numero"], name="parcela_numero_unico"),
            models.CheckConstraint(condition=Q(valor__gt=0), name="parcela_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.lancamento.descricao} {self.numero}/{self.lancamento.parcelas.count()}"

    def valores(self):
        """(principal paid, balance) computed from the payments (not annotated)."""
        pago = sum((p.principal for p in self.pagamentos.all() if not p.estornado), start=ZERO)
        return pago, self.valor - pago


class Pagamento(ModeloDaClinica):
    """Money received (or paid) for an installment. Partial payments are allowed.

    `valor` is what changed hands; `juros` (late fee, typed by hand) is included in it and
    `desconto` (administrators only) reduces what is owed: the installment is reduced by
    valor - juros + desconto.
    """

    class Forma(models.TextChoices):
        DINHEIRO = "dinheiro", _("Dinheiro")
        PIX = "pix", _("Pix")
        DEBITO = "debito", _("Cartão de débito")
        CREDITO = "credito", _("Cartão de crédito")
        TRANSFERENCIA = "transferencia", _("Transferência")
        BOLETO = "boleto", _("Boleto")
        CHEQUE = "cheque", _("Cheque")

    parcela = models.ForeignKey(
        Parcela, on_delete=models.PROTECT, related_name="pagamentos", verbose_name=_("parcela")
    )
    data = models.DateField(_("data"), default=timezone.localdate)
    valor = models.DecimalField(_("valor recebido"), **DINHEIRO)
    juros = models.DecimalField(
        _("juros e multa"),
        default=ZERO,
        help_text=_("Já incluídos no valor recebido."),
        **DINHEIRO,
    )
    desconto = models.DecimalField(_("desconto"), default=ZERO, **DINHEIRO)
    forma = models.CharField(_("forma de pagamento"), max_length=15, choices=Forma.choices)
    conta = models.ForeignKey(
        Conta, on_delete=models.PROTECT, related_name="+", verbose_name=_("conta")
    )
    # Card details only: never the card number.
    cartao_bandeira = models.CharField(_("bandeira do cartão"), max_length=30, blank=True)
    cartao_parcelas = models.PositiveSmallIntegerField(
        _("parcelas no cartão"), null=True, blank=True
    )
    cartao_codigo = models.CharField(_("código da transação (NSU)"), max_length=40, blank=True)
    observacao = models.CharField(_("observação"), max_length=200, blank=True)
    estornado = models.BooleanField(_("estornado"), default=False)
    estornado_em = models.DateTimeField(_("estornado em"), null=True, blank=True)
    estornado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estornado por"),
    )
    motivo_estorno = models.CharField(_("motivo do estorno"), max_length=200, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("recebido por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("pagamento")
        verbose_name_plural = _("pagamentos")
        ordering = ["-data", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="pagamento_valor_positivo"),
            models.CheckConstraint(condition=Q(juros__gte=0), name="pagamento_juros_positivo"),
            models.CheckConstraint(
                condition=Q(desconto__gte=0), name="pagamento_desconto_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.parcela} – {self.valor}"

    @property
    def principal(self):
        return self.valor - self.juros + self.desconto
