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


class TipoFinanceiro(models.TextChoices):
    RECEITA = "receita", _("Receita")
    DESPESA = "despesa", _("Despesa")


class GrupoContabil(ModeloDaClinica):
    """A node of the chart of accounts (decision 097, legacy Medical grupocontabil):
    groups hold subgroups and categories; entries go to the categories (the leaves)."""

    Tipo = TipoFinanceiro

    nome = models.CharField(_("nome"), max_length=60)
    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="filhos",
        verbose_name=_("grupo acima"),
    )
    codigo = models.PositiveSmallIntegerField(
        _("código"),
        null=True,
        blank=True,
        help_text=_("Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1."),
    )
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("grupo contábil")
        verbose_name_plural = _("grupos contábeis")
        ordering = ["tipo", "codigo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "tipo", "pai", "nome"], name="grupo_contabil_unico"
            )
        ]

    def __str__(self):
        return f"{self.numero} {self.nome}" if self.numero else self.nome

    def ancestrais(self):
        """From the top group down to the parent of this one."""
        cadeia, atual = [], self.pai
        while atual is not None:
            cadeia.insert(0, atual)
            atual = atual.pai
        return cadeia

    @property
    def numero(self):
        codigos = [g.codigo for g in [*self.ancestrais(), self]]
        return ".".join(map(str, codigos)) if None not in codigos else ""


class Categoria(ModeloDaClinica):
    """Grouping of income and expenses for the reports."""

    Tipo = TipoFinanceiro

    nome = models.CharField(_("nome"), max_length=60)
    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    grupo = models.ForeignKey(
        GrupoContabil,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categorias",
        verbose_name=_("grupo"),
    )
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


class CentroCusto(ModeloDaClinica):
    """Who in the clinic an entry is for (decision 095): a room, a specialty, the office.

    Optional on every entry, one per entry (no split across centers yet).
    """

    nome = models.CharField(_("nome"), max_length=60)
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("centro de custo")
        verbose_name_plural = _("centros de custo")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "nome"], name="centro_custo_unico")
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
    ("Comissões", Categoria.Tipo.DESPESA),
    ("Impostos", Categoria.Tipo.DESPESA),
    ("Água, luz e internet", Categoria.Tipo.DESPESA),
    ("Manutenção", Categoria.Tipo.DESPESA),
    ("Outras despesas", Categoria.Tipo.DESPESA),
]
# A basic chart of accounts for new clinics (decision 097): code, group and its categories.
PLANO_PADRAO = {
    Categoria.Tipo.RECEITA: [
        (1, "Atendimentos", ["Tratamento", "Consulta"]),
        (2, "Outras receitas", ["Outras receitas"]),
    ],
    Categoria.Tipo.DESPESA: [
        (1, "Ocupação", ["Aluguel", "Água, luz e internet", "Manutenção"]),
        (2, "Pessoal", ["Salários e encargos", "Comissões"]),
        (3, "Materiais e laboratório", ["Material odontológico", "Laboratório de prótese"]),
        (4, "Impostos", ["Impostos"]),
        (5, "Outras despesas", ["Outras despesas"]),
    ],
}


def criar_padroes(clinica):
    """Default accounts and categories for a clinic that has none."""
    with sem_isolamento():
        if not Conta.objects.filter(clinica=clinica).exists():
            Conta.objects.bulk_create(
                Conta(clinica=clinica, nome=nome, tipo=tipo) for nome, tipo in CONTAS_PADRAO
            )
        if not Categoria.objects.filter(clinica=clinica).exists():
            grupo_de = {}
            for tipo, linhas in PLANO_PADRAO.items():
                for codigo, nome, categorias in linhas:
                    grupo = GrupoContabil.objects.create(
                        clinica=clinica, tipo=tipo, codigo=codigo, nome=nome
                    )
                    grupo_de.update({(tipo, categoria): grupo for categoria in categorias})
            Categoria.objects.bulk_create(
                Categoria(clinica=clinica, nome=nome, tipo=tipo, grupo=grupo_de.get((tipo, nome)))
                for nome, tipo in CATEGORIAS_PADRAO
            )


class Fornecedor(ModeloDaClinica):
    """Who the clinic buys from or pays (decision 093), picked on a payable."""

    class Tipo(models.TextChoices):
        FISICA = "PF", _("Pessoa física")
        JURIDICA = "PJ", _("Pessoa jurídica")

    tipo = models.CharField(_("tipo"), max_length=2, choices=Tipo.choices, default=Tipo.JURIDICA)
    nome = models.CharField(
        _("nome"), max_length=200, help_text=_("Para pessoa jurídica, o nome fantasia.")
    )
    razao_social = models.CharField(_("razão social"), max_length=200, blank=True)
    cpf_cnpj = models.CharField(_("CPF/CNPJ"), max_length=14, blank=True)
    telefone = models.CharField(_("telefone"), max_length=11, blank=True)
    whatsapp = models.CharField(_("WhatsApp"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    observacoes = models.TextField(_("observações"), blank=True)
    ativo = models.BooleanField(_("ativo"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("fornecedor")
        verbose_name_plural = _("fornecedores")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "cpf_cnpj"],
                condition=~Q(cpf_cnpj=""),
                name="fornecedor_cpf_cnpj_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.nome


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
    centro_custo = models.ForeignKey(
        CentroCusto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("centro de custo"),
    )
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("paciente"),
    )
    # Who pays (receivable without a registered patient) or the supplier (payable). With a
    # registered supplier it holds the supplier's name, so lists and reports need no join.
    pessoa = models.CharField(_("pagador"), max_length=200, blank=True)
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lancamentos",
        verbose_name=_("fornecedor"),
    )
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
    # Practitioner commission (0.19.0): the commission that paid this receipt out, and the
    # one that deducted it again after it was reversed.
    comissao = models.ForeignKey(
        "Comissao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos",
        verbose_name=_("comissão"),
    )
    comissao_estorno = models.ForeignKey(
        "Comissao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos_estornados",
        verbose_name=_("comissão que descontou o estorno"),
    )
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


class Caixa(ModeloDaClinica):
    """A cash drawer session (0.17.0): opened with a counted amount, closed with another.

    While open, payments registered into its account, withdrawals and top-ups make up the
    expected amount; at closing the expected and counted amounts are stored, so later
    reversals do not change a closed session.
    """

    conta = models.ForeignKey(
        Conta, on_delete=models.PROTECT, related_name="caixas", verbose_name=_("conta")
    )
    aberto_em = models.DateTimeField(_("aberto em"), default=timezone.now)
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("aberto por"),
    )
    valor_abertura = models.DecimalField(_("valor contado na abertura"), **DINHEIRO)
    fechado_em = models.DateTimeField(_("fechado em"), null=True, blank=True)
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("fechado por"),
    )
    valor_esperado = models.DecimalField(_("valor esperado"), null=True, blank=True, **DINHEIRO)
    valor_contado = models.DecimalField(
        _("valor contado no fechamento"), null=True, blank=True, **DINHEIRO
    )
    observacao = models.CharField(_("observação"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("caixa")
        verbose_name_plural = _("caixas")
        ordering = ["-aberto_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["conta"],
                condition=Q(fechado_em__isnull=True),
                name="um_caixa_aberto_por_conta",
            ),
            models.CheckConstraint(
                condition=Q(valor_abertura__gte=0), name="caixa_abertura_positiva"
            ),
        ]

    def __str__(self):
        return f"{self.conta} {timezone.localtime(self.aberto_em):%d/%m/%Y %H:%M}"

    @property
    def aberto(self):
        return self.fechado_em is None

    @property
    def diferenca(self):
        if self.valor_contado is None or self.valor_esperado is None:
            return None
        return self.valor_contado - self.valor_esperado


class MovimentoCaixa(ModeloDaClinica):
    """Withdrawal from or top-up of an open cash drawer, optionally to/from another account."""

    class Tipo(models.TextChoices):
        RETIRADA = "retirada", _("Retirada (sangria)")
        REFORCO = "reforco", _("Reforço")

    caixa = models.ForeignKey(
        Caixa, on_delete=models.PROTECT, related_name="movimentos", verbose_name=_("caixa")
    )
    tipo = models.CharField(_("tipo"), max_length=10, choices=Tipo.choices)
    valor = models.DecimalField(_("valor"), **DINHEIRO)
    outra_conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("outra conta"),
        help_text=_("Para onde vai a retirada ou de onde vem o reforço (vazio: fora do sistema)."),
    )
    motivo = models.CharField(_("motivo"), max_length=200)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("movimento de caixa")
        verbose_name_plural = _("movimentos de caixa")
        ordering = ["criado_em"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="movimento_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.valor}"


class Comissao(ModeloDaClinica):
    """A practitioner commission paid out (0.19.0, decision 053).

    It covers every receipt of the practitioner's receivables up to `ate` not covered
    before, minus the commission of receipts reversed after being paid out. Paying it
    creates a payable; cancelling that payable cancels the commission and frees the receipts.
    """

    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="comissoes",
        verbose_name=_("profissional"),
    )
    ate = models.DateField(_("recebimentos até"))
    percentual = models.DecimalField(_("percentual"), max_digits=5, decimal_places=2)
    recebido = models.DecimalField(_("valor recebido"), **DINHEIRO)
    estornos = models.DecimalField(_("comissão de estornos descontada"), default=ZERO, **DINHEIRO)
    valor = models.DecimalField(_("valor da comissão"), **DINHEIRO)
    lancamento = models.OneToOneField(
        Lancamento,
        on_delete=models.PROTECT,
        related_name="comissao",
        verbose_name=_("lançamento a pagar"),
    )
    cancelada = models.BooleanField(_("cancelada"), default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("comissão")
        verbose_name_plural = _("comissões")
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="comissao_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.profissional} {self.ate:%d/%m/%Y}"

    @property
    def bruta(self):
        """Commission on the receipts, before deducting reversals."""
        return self.valor + self.estornos


class Fechamento(ModeloDaClinica):
    """Finance closed up to a date (decision 096), so the reports given to the accountant
    do not change: no payment dated on or before it can be recorded or reversed.

    Each row is a closing or a reopening, kept as history; the newest one rules. A
    reopening has an earlier date (or none: everything open) and a reason.
    """

    ate = models.DateField(_("fechado até"), null=True, blank=True)
    motivo = models.CharField(_("motivo"), max_length=200, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("fechamento do financeiro")
        verbose_name_plural = _("fechamentos do financeiro")
        ordering = ["-criado_em", "-pk"]

    def __str__(self):
        return f"{self.ate:%d/%m/%Y}" if self.ate else str(_("Aberto"))


class ImportacaoExtrato(ModeloDaClinica):
    """One OFX file imported into a bank account (0.20.0, decision 054)."""

    conta = models.ForeignKey(
        Conta, on_delete=models.PROTECT, related_name="importacoes", verbose_name=_("conta")
    )
    arquivo = models.CharField(_("arquivo"), max_length=200)
    banco = models.CharField(_("código do banco"), max_length=20, blank=True)
    conta_no_banco = models.CharField(_("conta no banco"), max_length=40, blank=True)
    inicio = models.DateField(_("início"), null=True, blank=True)
    fim = models.DateField(_("fim"), null=True, blank=True)
    saldo = models.DecimalField(_("saldo no banco"), null=True, blank=True, **DINHEIRO)
    saldo_em = models.DateField(_("saldo em"), null=True, blank=True)
    novas = models.PositiveIntegerField(_("transações novas"), default=0)
    repetidas = models.PositiveIntegerField(_("transações já importadas"), default=0)
    ignoradas = models.PositiveIntegerField(
        _("transações ilegíveis"),
        default=0,
        help_text=_("Linhas do arquivo sem data ou valor que dê para ler: não foram importadas."),
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("importado por"),
    )
    criado_em = models.DateTimeField(_("importado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("importação de extrato")
        verbose_name_plural = _("importações de extrato")
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.conta} {self.arquivo}"


class TransacaoBancaria(ModeloDaClinica):
    """A bank statement line, reconciled with a payment or a drawer movement, or ignored."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", _("Pendente")
        CONCILIADA = "conciliada", _("Conciliada")
        IGNORADA = "ignorada", _("Ignorada")

    conta = models.ForeignKey(
        Conta, on_delete=models.PROTECT, related_name="transacoes", verbose_name=_("conta")
    )
    importacao = models.ForeignKey(
        ImportacaoExtrato,
        on_delete=models.PROTECT,
        related_name="transacoes",
        verbose_name=_("importação"),
    )
    fitid = models.CharField(_("identificador no banco"), max_length=120)
    data = models.DateField(_("data"))
    valor = models.DecimalField(
        _("valor"), help_text=_("Positivo: entrada; negativo: saída."), **DINHEIRO
    )
    descricao = models.CharField(_("descrição"), max_length=200, blank=True)
    tipo = models.CharField(_("tipo no banco"), max_length=20, blank=True)
    situacao = models.CharField(
        _("situação"), max_length=10, choices=Situacao.choices, default=Situacao.PENDENTE
    )
    pagamento = models.OneToOneField(
        Pagamento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacao",
        verbose_name=_("pagamento"),
    )
    movimento = models.OneToOneField(
        MovimentoCaixa,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transacao",
        verbose_name=_("movimento do caixa"),
    )
    motivo = models.CharField(_("motivo"), max_length=200, blank=True)
    conciliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("conciliado por"),
    )
    conciliado_em = models.DateTimeField(_("conciliado em"), null=True, blank=True)

    class Meta:
        verbose_name = _("transação bancária")
        verbose_name_plural = _("transações bancárias")
        ordering = ["data", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["conta", "fitid"], name="transacao_unica_por_conta"),
            models.CheckConstraint(
                condition=~Q(pagamento__isnull=False, movimento__isnull=False),
                name="transacao_um_vinculo",
            ),
        ]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} {self.valor} {self.descricao}"

    @property
    def entrada(self):
        return self.valor > 0
