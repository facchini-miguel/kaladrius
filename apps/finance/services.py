"""Financial rules: installments, receiving, reversing, cancelling and debtors."""

import calendar
import datetime
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import pgettext

from apps.core.models import Clinic
from apps.core.ordering import chave_alfabetica

from . import commissions
from .models import (
    ZERO,
    AccountGroup,
    BankTransaction,
    BookClosing,
    CashMovement,
    CashRegister,
    Category,
    Commission,
    CostCenter,
    Entry,
    Installment,
    Payment,
    Planning,
)
from .payment_methods import rotulos as rotulos_das_formas

CENTAVO = Decimal("0.01")
DINHEIRO = DecimalField(max_digits=12, decimal_places=2)
# Days overdue for the debtors report: up to 30, 31-60, 61-90, over 90.
FAIXAS_DE_ATRASO = [30, 60, 90]


def dividir(total, quantidade):
    """Equal installments; the leftover cents go to the first one."""
    base = (total / quantidade).quantize(CENTAVO, rounding=ROUND_DOWN)
    valores = [base] * quantidade
    valores[0] += total - base * quantidade
    return valores


def somar_meses(date, meses):
    """Same day N months later (the 31st becomes the last day of shorter months)."""
    ano, mes = divmod(date.month - 1 + meses, 12)
    ano, mes = date.year + ano, mes + 1
    return date.replace(year=ano, month=mes, day=min(date.day, calendar.monthrange(ano, mes)[1]))


@transaction.atomic
def criar_lancamento(*, parcelas, primeiro_vencimento, user, **campos):
    """Create an entry with `parcelas` monthly installments from `primeiro_vencimento`."""
    entry = Entry.objects.create(created_by=user, **campos)
    # One by one (at most 48), not bulk_create, so the audit log records each installment.
    for number, amount in enumerate(dividir(entry.valor_total, parcelas), start=1):
        Installment.objects.create(
            clinic=entry.clinic,
            entry=entry,
            number=number,
            vencimento=somar_meses(primeiro_vencimento, number - 1),
            amount=amount,
        )
    return entry


@transaction.atomic
def receber(parcela, *, user, **campos):
    """Record a payment for an installment. Raises ValidationError if it exceeds the balance.

    The installment row is locked, so two people receiving at once cannot overpay it.
    """
    parcela = Installment.objects.select_for_update().select_related("entry").get(pk=parcela.pk)
    if parcela.entry.cancelado:
        raise ValidationError(_("Este lançamento foi cancelado."))
    pagamento = Payment(clinic=parcela.clinic, parcela=parcela, created_by=user, **campos)
    conferir_periodo(pagamento.clinic_id, pagamento.date)
    _pago, saldo = parcela.valores()
    if pagamento.principal <= 0:
        raise ValidationError(_("O valor abatido da parcela precisa ser maior que zero."))
    if pagamento.principal > saldo:
        raise ValidationError(
            _("O valor abatido (%(abatido)s) passa do que falta na parcela (%(saldo)s).")
            % {"abatido": pagamento.principal, "saldo": saldo}
        )
    pagamento.save()
    return pagamento


@transaction.atomic
def estornar(pagamento, *, reason, user):
    pagamento = Payment.objects.select_for_update().get(pk=pagamento.pk)
    if pagamento.estornado:
        raise ValidationError(_("Este pagamento já foi estornado."))
    conferir_periodo(pagamento.clinic_id, pagamento.date)
    pagamento.estornado = True
    pagamento.estornado_em = timezone.now()
    pagamento.estornado_por = user
    pagamento.motivo_estorno = reason
    # Only these fields: the commission links are set elsewhere and must not be overwritten.
    pagamento.save(update_fields=["estornado", "estornado_em", "estornado_por", "motivo_estorno"])
    # A reversed payment no longer explains its bank statement line (saved, not .update(),
    # so the audit log records it).
    for transacao in BankTransaction.objects.filter(pagamento=pagamento):
        transacao.pagamento = None
        transacao.status = BankTransaction.Situacao.PENDENTE
        transacao.conciliado_por = None
        transacao.conciliado_em = None
        transacao.save()
    return pagamento


@transaction.atomic
def cancelar(entry, *, reason, user):
    """Cancel an entry. Payments must be reversed first (they are real money).

    The entry row is locked: receber() locks it too (through its installment), so a
    payment cannot be recorded while the entry is being cancelled.
    """
    entry = Entry.objects.select_for_update().get(pk=entry.pk)
    if entry.cancelado:
        raise ValidationError(_("Este lançamento já foi cancelado."))
    if Payment.objects.filter(parcela__entry=entry, estornado=False).exists():
        raise ValidationError(
            _("Este lançamento tem pagamentos. Estorne os pagamentos antes de cancelar.")
        )
    comissao = Commission.objects.filter(entry=entry, cancelada=False).first()
    if comissao is not None:
        commissions.liberar(comissao)  # raises ValidationError when it cannot be undone
    entry.cancelado = True
    entry.cancelado_em = timezone.now()
    entry.cancelado_por = user
    entry.motivo_cancelamento = reason
    entry.save()
    return entry


# --- Closing the books (decision 096) -------------------------------------------------


def fechado_ate(clinic_id):
    """Last day of the clinic's closed period, or None. Explicit clinic: also called by
    commands that run without the request's isolation."""
    ultimo = BookClosing.todos.filter(clinic_id=clinic_id).first()  # newest first
    return ultimo.until if ultimo else None


def conferir_periodo(clinic_id, date):
    """Refuse money dated inside the closed period. Locks the clinic row, shared with
    fechar(), so a payment cannot slip in while the period is being closed."""
    Clinic.objects.select_for_update().get(pk=clinic_id)
    until = fechado_ate(clinic_id)
    if until is not None and date <= until:
        raise ValidationError(
            _(
                "O financeiro está fechado até %(ate)s: pagamentos e estornos nessa data ou "
                "antes dela não podem ser registrados. Use uma data posterior ou peça ao "
                "administrador para reabrir o período."
            )
            % {"ate": date_format(until, "SHORT_DATE_FORMAT")}
        )


@transaction.atomic
def fechar(clinic, until, *, user):
    """Close the books up to `ate` (at most yesterday: today's cash is still moving)."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    if until >= timezone.localdate():
        raise ValidationError(_("Feche no máximo até ontem: hoje ainda há movimento."))
    atual = fechado_ate(clinic.pk)
    if atual is not None and until <= atual:
        raise ValidationError(
            _("O financeiro já está fechado até %(ate)s. Para voltar, reabra o período.")
            % {"ate": date_format(atual, "SHORT_DATE_FORMAT")}
        )
    return BookClosing.objects.create(clinic=clinic, until=until, created_by=user)


@transaction.atomic
def reabrir(clinic, until, *, reason, user):
    """Move the closing back to `ate` (None opens everything). A reason is required."""
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    atual = fechado_ate(clinic.pk)
    if atual is None:
        raise ValidationError(_("O financeiro não está fechado."))
    if until is not None and until >= atual:
        raise ValidationError(_("Para reabrir, escolha uma data anterior ao fechamento atual."))
    if not reason.strip():
        raise ValidationError(_("Informe o motivo da reabertura."))
    return BookClosing.objects.create(
        clinic=clinic, until=until, reason=reason.strip(), created_by=user
    )


def status(parcela, hoje=None):
    """Status of an installment annotated with com_saldo() (code, label)."""
    hoje = hoje or timezone.localdate()
    if parcela.entry.cancelado:
        return "cancelada", _("Cancelada")
    if parcela.saldo <= 0:
        return "paga", _("Paga")
    if parcela.vencimento < hoje:
        return "vencida", _("Vencida")
    if parcela.pago > 0:
        return "parcial", _("Paga em parte")
    return "aberta", pgettext("parcela", "Em aberto")


def devedores(hoje=None):
    """Who owes the clinic, from the open installments of receivables.

    One row per patient (or payer name): overdue total split by days late, amount not yet
    due and the oldest due date, ordered by the overdue total.
    """
    hoje = hoje or timezone.localdate()
    # Plain values, not model instances: a clinic with years of use has thousands of open
    # installments, and full objects took tens of MB per request (volume test, decision 108).
    parcelas = (
        Installment.objects.abertas()
        .filter(entry__kind=Entry.Tipo.RECEBER)
        .values(
            "vencimento",
            "saldo",
            "entry__patient_id",
            "entry__patient__name",
            "entry__pessoa",
        )
    )
    linhas = defaultdict(
        lambda: {
            "patient_id": None,
            "name": "",
            "faixas": [ZERO] * (len(FAIXAS_DE_ATRASO) + 1),
            "vencido": ZERO,
            "a_vencer": ZERO,
            "mais_antigo": None,
        }
    )
    for parcela in parcelas:
        patient_id = parcela["entry__patient_id"]
        pessoa = parcela["entry__pessoa"]
        chave = ("patient", patient_id) if patient_id else ("pessoa", pessoa.strip().lower())
        linha = linhas[chave]
        linha["patient_id"] = patient_id
        linha["name"] = parcela["entry__patient__name"] if patient_id else pessoa
        vencimento, saldo = parcela["vencimento"], parcela["saldo"]
        if vencimento >= hoje:
            linha["a_vencer"] += saldo
            continue
        atraso = (hoje - vencimento).days
        faixa = next(
            (i for i, limite in enumerate(FAIXAS_DE_ATRASO) if atraso <= limite),
            len(FAIXAS_DE_ATRASO),
        )
        linha["faixas"][faixa] += saldo
        linha["vencido"] += saldo
        if linha["mais_antigo"] is None or vencimento < linha["mais_antigo"]:
            linha["mais_antigo"] = vencimento
    resultado = [linha for linha in linhas.values() if linha["vencido"] or linha["a_vencer"]]
    return sorted(resultado, key=lambda linha: (-linha["vencido"], chave_alfabetica(linha["name"])))


def resumo_do_paciente(patient, hoje=None):
    """Open installments, totals and latest payments of a patient (for the record)."""
    hoje = hoje or timezone.localdate()
    abertas = list(
        Installment.objects.abertas()
        .filter(entry__patient=patient, entry__kind=Entry.Tipo.RECEBER)
        .select_related("entry")
        .order_by("vencimento")
    )
    return {
        "abertas": abertas,
        "vencido": sum((p.saldo for p in abertas if p.vencimento < hoje), start=ZERO),
        "a_vencer": sum((p.saldo for p in abertas if p.vencimento >= hoje), start=ZERO),
        "pagamentos": list(
            Payment.objects.filter(parcela__entry__patient=patient)
            .select_related("parcela__entry", "account")
            .order_by("-date", "-pk")[:5]
        ),
    }


# --- Cash flow and reports (0.16.0) ------------------------------------------------------


def _sinal(kind):
    """Receivables bring money in (+), payables take it out (-)."""
    return 1 if kind == Entry.Tipo.RECEBER else -1


def pagamentos_validos():
    return Payment.objects.filter(estornado=False, parcela__entry__cancelado=False)


def saldos_das_contas(until=None):
    """[(account, balance)] = initial balance + money in - money out (payments up to `ate`).

    Summed in the database, grouped by account, so it does not grow with the history.
    """
    from .models import FinancialAccount

    pagamentos = pagamentos_validos()
    if until is not None:
        pagamentos = pagamentos.filter(date__lte=until)
    movimento = defaultdict(lambda: ZERO)
    for account_id, kind, total in (
        pagamentos.order_by()
        .values_list("account_id", "parcela__entry__kind")
        .annotate(total=Sum("amount"))
    ):
        movimento[account_id] += _sinal(kind) * total
    movimentos = CashMovement.objects.all()
    if until is not None:
        movimentos = movimentos.filter(created_at__date__lte=until)
    for account_id, outra_id, kind, total in (
        movimentos.order_by()
        .values_list("caixa__account_id", "outra_conta_id", "kind")
        .annotate(total=Sum("amount"))
    ):
        # A withdrawal leaves the drawer (into the other account, if any); a top-up enters it.
        sinal = -1 if kind == CashMovement.Tipo.RETIRADA else 1
        movimento[account_id] += sinal * total
        if outra_id:
            movimento[outra_id] -= sinal * total
    return [
        (account, account.saldo_inicial + movimento[account.pk])
        for account in FinancialAccount.objects.all().order_by("name")
    ]


def fluxo_de_caixa(de, until, por_mes=False, hoje=None):
    """Rows per day (or month) from `de` to `ate`.

    Actual = payments made (by payment date); expected = what is still open in the
    installments due in the period (overdue ones included, flagged by the date). The
    running balance starts from the accounts' balance on the day before `de` and adds both.
    """
    hoje = hoje or timezone.localdate()

    def chave(date):
        return date.replace(day=1) if por_mes else date

    linhas = defaultdict(
        lambda: {
            "entradas": ZERO,
            "saidas": ZERO,
            "entradas_previstas": ZERO,
            "saidas_previstas": ZERO,
        }
    )
    for date, kind, amount in (
        pagamentos_validos()
        .filter(date__gte=de, date__lte=until)
        .values_list("date", "parcela__entry__kind", "amount")
    ):
        linhas[chave(date)]["entradas" if kind == Entry.Tipo.RECEBER else "saidas"] += amount
    # Drawer movements to or from outside the system (moves between accounts net to zero).
    for timestamp, kind, amount in CashMovement.objects.filter(
        outra_conta__isnull=True, created_at__date__gte=de, created_at__date__lte=until
    ).values_list("created_at", "kind", "amount"):
        date = timezone.localtime(timestamp).date()
        linhas[chave(date)]["saidas" if kind == CashMovement.Tipo.RETIRADA else "entradas"] += (
            amount
        )
    for parcela in (
        Installment.objects.abertas()
        .filter(vencimento__gte=de, vencimento__lte=until)
        .select_related("entry")
    ):
        campo = (
            "entradas_previstas" if parcela.entry.kind == Entry.Tipo.RECEBER else "saidas_previstas"
        )
        linhas[chave(parcela.vencimento)][campo] += parcela.saldo

    anterior = de - datetime.timedelta(days=1)
    saldo_inicial = sum(
        (amount for _conta, amount in saldos_das_contas(until=anterior)), start=ZERO
    )
    saldo = saldo_inicial
    resultado = []
    for date in sorted(linhas):
        linha = linhas[date]
        linha["date"] = date
        linha["atrasado"] = (
            not por_mes
            and date < hoje
            and (linha["entradas_previstas"] or linha["saidas_previstas"])
        )
        saldo += (
            linha["entradas"]
            - linha["saidas"]
            + linha["entradas_previstas"]
            - linha["saidas_previstas"]
        )
        linha["saldo"] = saldo
        resultado.append(linha)
    totais = {
        campo: sum((linha[campo] for linha in resultado), start=ZERO)
        for campo in ("entradas", "saidas", "entradas_previstas", "saidas_previstas")
    }
    return {
        "linhas": resultado,
        "totais": totais,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldo,
    }


def recebido_e_pago(de, until):
    """(money received, money paid) from `de` to `ate`, in one query (home page, 0.24.0)."""
    totais = dict(
        pagamentos_validos()
        .filter(date__gte=de, date__lte=until)
        .order_by()
        .values_list("parcela__entry__kind")
        .annotate(total=Sum("amount"))
    )
    return totais.get(Entry.Tipo.RECEBER, ZERO), totais.get(Entry.Tipo.PAGAR, ZERO)


def relatorio(de, until):
    """Money received and paid in the period, grouped for the reports page."""
    pagamentos = pagamentos_validos().filter(date__gte=de, date__lte=until)
    recebidos = pagamentos.filter(parcela__entry__kind=Entry.Tipo.RECEBER)
    pagos = pagamentos.filter(parcela__entry__kind=Entry.Tipo.PAGAR)

    def agrupar(consulta, campo, rotulo=None):
        grupos = consulta.order_by().values_list(campo).annotate(total=Sum("amount"))
        linhas = [((rotulo or {}).get(chave, chave), total) for chave, total in grupos]
        return sorted(linhas, key=lambda linha: -linha[1])

    def somar(consulta, campo):
        return consulta.aggregate(total=Coalesce(Sum(campo), ZERO, output_field=DINHEIRO))["total"]

    formas = rotulos_das_formas()
    total_recebido = somar(recebidos, "amount")
    total_pago = somar(pagos, "amount")
    # The chart of accounts (decision 097) only once the clinic has groups.
    grupos = AccountGroup.objects.exists()
    # Cost centers (decision 095) only once the clinic has registered one.
    centros = CostCenter.objects.exists()
    sem_centro = {None: _("Sem centro de custo")}
    centro = "parcela__entry__centro_custo__name"
    return {
        "grupos": grupos,
        "por_grupo": arvore_por_grupo(recebidos, Category.Tipo.RECEITA) if grupos else [],
        "despesas_por_grupo": arvore_por_grupo(pagos, Category.Tipo.DESPESA) if grupos else [],
        "centros": centros,
        "por_centro": agrupar(recebidos, centro, sem_centro) if centros else [],
        "despesas_por_centro": agrupar(pagos, centro, sem_centro) if centros else [],
        "por_forma": agrupar(recebidos, "forma", formas),
        "por_categoria": agrupar(recebidos, "parcela__entry__category__name"),
        "por_profissional": agrupar(recebidos, "parcela__entry__practitioner__name"),
        "despesas_por_categoria": agrupar(pagos, "parcela__entry__category__name"),
        "total_recebido": total_recebido,
        "total_pago": total_pago,
        "resultado": total_recebido - total_pago,
        "descontos": somar(recebidos, "discount"),
        "juros": somar(recebidos, "juros"),
    }


def ligar_grupos(consulta):
    """The groups with each parent set from the same list, so numbers like 2.1 are
    built without one query per level."""
    grupos = list(consulta)
    por_id = {group.pk: group for group in grupos}
    for group in grupos:
        if group.pai_id in por_id:
            group.pai = por_id[group.pai_id]
    return grupos


def em_ordem_de_arvore(grupos):
    """(level, group) pairs in chart order: each group followed by its subgroups."""
    filhos = defaultdict(list)
    for group in grupos:  # already in chart order (code, then name)
        filhos[group.pai_id].append(group)
    saida = []

    def descer(pai_id, nivel):
        for group in filhos[pai_id]:
            saida.append((nivel, group))
            descer(group.pk, nivel + 1)

    descer(None, 0)
    return saida


def totais_por_grupo(pagamentos, kind):
    """Payments summed by group, each group including its subgroups.

    Returns (groups of the type, {group id: total}, total of categories outside any group).
    """
    por_categoria = dict(
        pagamentos.order_by()
        .values_list("parcela__entry__category_id")
        .annotate(total=Sum("amount"))
    )
    grupo_da_categoria = dict(Category.objects.filter(kind=kind).values_list("pk", "group_id"))
    grupos = ligar_grupos(AccountGroup.objects.filter(kind=kind))
    pai = {group.pk: group.pai_id for group in grupos}
    totais = defaultdict(lambda: ZERO)
    sem_grupo = ZERO
    for category_id, amount in por_categoria.items():
        group_id = grupo_da_categoria.get(category_id)
        if group_id is None:
            sem_grupo += amount
        while group_id is not None:
            totais[group_id] += amount
            group_id = pai.get(group_id)
    return grupos, totais, sem_grupo


def arvore_por_grupo(pagamentos, kind):
    """(level, name, total) rows in tree order for the reports, groups without money left
    out, and a last row for the categories outside any group."""
    grupos, totais, sem_grupo = totais_por_grupo(pagamentos, kind)
    linhas = [
        (nivel, str(group), totais[group.pk])
        for nivel, group in em_ordem_de_arvore(grupos)
        if totais[group.pk]
    ]
    if sem_grupo:
        linhas.append((0, _("Sem grupo"), sem_grupo))
    return linhas


# --- Yearly planning (decision 098) ---------------------------------------------------


def fracao_do_ano(ano, hoje=None):
    """Share of the year already gone: 0 before it starts, 1 once it is over."""
    hoje = hoje or timezone.localdate()
    start, end = datetime.date(ano, 1, 1), datetime.date(ano, 12, 31)
    if hoje < start:
        return Decimal(0)
    if hoje >= end:
        return Decimal(1)
    return Decimal((hoje - start).days + 1) / Decimal((end - start).days + 1)


def planejamento(ano, hoje=None):
    """Goals of the year next to what was received and paid, group by group.

    "Esperado" is the goal times the share of the year gone, so mid-year a group can be
    compared with where it should be. Section totals add the goals of the highest groups
    that have one, so a goal and its subgroups' goals are not counted twice.
    """
    fracao = fracao_do_ano(ano, hoje)
    metas = dict(Planning.objects.filter(ano=ano).values_list("group_id", "amount"))
    pagamentos = pagamentos_validos().filter(date__year=ano)
    secoes = []
    for kind, rotulo, lancamentos in (
        (Category.Tipo.RECEITA, _("Receitas"), Entry.Tipo.RECEBER),
        (Category.Tipo.DESPESA, _("Despesas"), Entry.Tipo.PAGAR),
    ):
        grupos, totais, sem_grupo = totais_por_grupo(
            pagamentos.filter(parcela__entry__kind=lancamentos), kind
        )
        linhas, meta_total, cobertos = [], ZERO, set()
        for nivel, group in em_ordem_de_arvore(grupos):
            meta, realizado = metas.get(group.pk), totais[group.pk]
            if not group.active and meta is None and not realizado:
                continue
            if meta and group.pai_id not in cobertos:
                meta_total += meta
            if meta or group.pai_id in cobertos:
                cobertos.add(group.pk)
            esperado = (meta * fracao).quantize(CENTAVO) if meta else None
            linhas.append(
                {
                    "nivel": nivel,
                    "group": group,
                    "meta": meta,
                    "realizado": realizado,
                    "esperado": esperado,
                    "percentual": round(100 * realizado / meta) if meta else None,
                    # On track: income at or above where it should be, expenses at or below.
                    "em_dia": None
                    if not meta
                    else realizado >= esperado
                    if kind == Category.Tipo.RECEITA
                    else realizado <= esperado,
                }
            )
        realizado_total = sum((totais[g.pk] for g in grupos if g.pai_id is None), ZERO) + sem_grupo
        secoes.append(
            {
                "kind": kind,
                "rotulo": rotulo,
                "linhas": linhas,
                "sem_grupo": sem_grupo,
                "meta": meta_total,
                "esperado": (meta_total * fracao).quantize(CENTAVO),
                "realizado": realizado_total,
            }
        )
    return {"ano": ano, "fracao": fracao, "secoes": secoes}


@transaction.atomic
def salvar_metas(ano, valores):
    """{group: goal or None}: saves the goals, removing the ones left blank."""
    for group, amount in valores.items():
        if amount:
            Planning.objects.update_or_create(ano=ano, group=group, defaults={"amount": amount})
        else:
            Planning.objects.filter(ano=ano, group=group).delete()


@transaction.atomic
def copiar_metas(ano):
    """Copy last year's goals into the groups still without a goal; returns how many."""
    existentes = set(Planning.objects.filter(ano=ano).values_list("group_id", flat=True))
    copiadas = 0
    for anterior in Planning.objects.filter(ano=ano - 1).exclude(group_id__in=existentes):
        # One by one, not bulk_create, so the audit log records each goal.
        Planning.objects.create(ano=ano, group_id=anterior.group_id, amount=anterior.amount)
        copiadas += 1
    return copiadas


# --- Daily cash drawer (0.17.0) ----------------------------------------------------------


def caixa_aberto(account):
    return CashRegister.objects.filter(account=account, fechado_em__isnull=True).first()


@transaction.atomic
def abrir_caixa(account, *, amount, user):
    if caixa_aberto(account) is not None:
        raise ValidationError(_("O caixa desta conta já está aberto."))
    return CashRegister.objects.create(
        clinic=account.clinic, account=account, valor_abertura=amount, aberto_por=user
    )


def resumo_do_caixa(caixa):
    """Money that went through the drawer since it was opened, and the expected amount.

    Payments count by the moment they were registered (not their date), so a payment
    typed in today for last week still lands in today's drawer.
    """
    end = caixa.fechado_em or timezone.now()
    pagamentos = list(
        pagamentos_validos()
        .filter(account=caixa.account, created_at__gte=caixa.aberto_em, created_at__lte=end)
        .select_related("parcela__entry__patient")
        .order_by("created_at")
    )
    movimentos = list(caixa.movimentos.select_related("outra_conta", "created_by"))
    entradas = sum(
        (p.amount for p in pagamentos if p.parcela.entry.kind == Entry.Tipo.RECEBER),
        start=ZERO,
    )
    saidas = sum(
        (p.amount for p in pagamentos if p.parcela.entry.kind == Entry.Tipo.PAGAR),
        start=ZERO,
    )
    reforcos = sum(
        (m.amount for m in movimentos if m.kind == CashMovement.Tipo.REFORCO), start=ZERO
    )
    retiradas = sum(
        (m.amount for m in movimentos if m.kind == CashMovement.Tipo.RETIRADA), start=ZERO
    )
    return {
        "pagamentos": pagamentos,
        "movimentos": movimentos,
        "entradas": entradas,
        "saidas": saidas,
        "reforcos": reforcos,
        "retiradas": retiradas,
        "esperado": caixa.valor_abertura + entradas - saidas + reforcos - retiradas,
    }


@transaction.atomic
def movimentar_caixa(caixa, *, kind, amount, reason, user, outra_conta=None):
    caixa = CashRegister.objects.select_for_update().get(pk=caixa.pk)
    if not caixa.aberto:
        raise ValidationError(_("Este caixa já foi fechado."))
    if outra_conta is not None and outra_conta.pk == caixa.account_id:
        raise ValidationError(_("Escolha uma conta diferente da do caixa."))
    if kind == CashMovement.Tipo.RETIRADA and amount > resumo_do_caixa(caixa)["esperado"]:
        raise ValidationError(_("A retirada passa do valor que deveria estar no caixa."))
    return CashMovement.objects.create(
        clinic=caixa.clinic,
        caixa=caixa,
        kind=kind,
        amount=amount,
        reason=reason,
        outra_conta=outra_conta,
        created_by=user,
    )


@transaction.atomic
def fechar_caixa(caixa, *, valor_contado, note, user):
    caixa = CashRegister.objects.select_for_update().get(pk=caixa.pk)
    if not caixa.aberto:
        raise ValidationError(_("Este caixa já foi fechado."))
    caixa.valor_esperado = resumo_do_caixa(caixa)["esperado"]
    caixa.valor_contado = valor_contado
    caixa.note = note
    caixa.fechado_em = timezone.now()
    caixa.fechado_por = user
    caixa.save()
    return caixa
