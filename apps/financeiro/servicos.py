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

from apps.core.models import Clinica
from apps.core.ordem import chave_alfabetica

from . import comissoes
from .models import (
    ZERO,
    Caixa,
    Categoria,
    CentroCusto,
    Comissao,
    Fechamento,
    GrupoContabil,
    Lancamento,
    MovimentoCaixa,
    Pagamento,
    Parcela,
    Planejamento,
    TransacaoBancaria,
)

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


def somar_meses(data, meses):
    """Same day N months later (the 31st becomes the last day of shorter months)."""
    ano, mes = divmod(data.month - 1 + meses, 12)
    ano, mes = data.year + ano, mes + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


@transaction.atomic
def criar_lancamento(*, parcelas, primeiro_vencimento, usuario, **campos):
    """Create an entry with `parcelas` monthly installments from `primeiro_vencimento`."""
    lancamento = Lancamento.objects.create(criado_por=usuario, **campos)
    # One by one (at most 48), not bulk_create, so the audit log records each installment.
    for numero, valor in enumerate(dividir(lancamento.valor_total, parcelas), start=1):
        Parcela.objects.create(
            clinica=lancamento.clinica,
            lancamento=lancamento,
            numero=numero,
            vencimento=somar_meses(primeiro_vencimento, numero - 1),
            valor=valor,
        )
    return lancamento


@transaction.atomic
def receber(parcela, *, usuario, **campos):
    """Record a payment for an installment. Raises ValidationError if it exceeds the balance.

    The installment row is locked, so two people receiving at once cannot overpay it.
    """
    parcela = Parcela.objects.select_for_update().select_related("lancamento").get(pk=parcela.pk)
    if parcela.lancamento.cancelado:
        raise ValidationError(_("Este lançamento foi cancelado."))
    pagamento = Pagamento(clinica=parcela.clinica, parcela=parcela, criado_por=usuario, **campos)
    conferir_periodo(pagamento.clinica_id, pagamento.data)
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
def estornar(pagamento, *, motivo, usuario):
    pagamento = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
    if pagamento.estornado:
        raise ValidationError(_("Este pagamento já foi estornado."))
    conferir_periodo(pagamento.clinica_id, pagamento.data)
    pagamento.estornado = True
    pagamento.estornado_em = timezone.now()
    pagamento.estornado_por = usuario
    pagamento.motivo_estorno = motivo
    # Only these fields: the commission links are set elsewhere and must not be overwritten.
    pagamento.save(update_fields=["estornado", "estornado_em", "estornado_por", "motivo_estorno"])
    # A reversed payment no longer explains its bank statement line (saved, not .update(),
    # so the audit log records it).
    for transacao in TransacaoBancaria.objects.filter(pagamento=pagamento):
        transacao.pagamento = None
        transacao.situacao = TransacaoBancaria.Situacao.PENDENTE
        transacao.conciliado_por = None
        transacao.conciliado_em = None
        transacao.save()
    return pagamento


@transaction.atomic
def cancelar(lancamento, *, motivo, usuario):
    """Cancel an entry. Payments must be reversed first (they are real money).

    The entry row is locked: receber() locks it too (through its installment), so a
    payment cannot be recorded while the entry is being cancelled.
    """
    lancamento = Lancamento.objects.select_for_update().get(pk=lancamento.pk)
    if lancamento.cancelado:
        raise ValidationError(_("Este lançamento já foi cancelado."))
    if Pagamento.objects.filter(parcela__lancamento=lancamento, estornado=False).exists():
        raise ValidationError(
            _("Este lançamento tem pagamentos. Estorne os pagamentos antes de cancelar.")
        )
    comissao = Comissao.objects.filter(lancamento=lancamento, cancelada=False).first()
    if comissao is not None:
        comissoes.liberar(comissao)  # raises ValidationError when it cannot be undone
    lancamento.cancelado = True
    lancamento.cancelado_em = timezone.now()
    lancamento.cancelado_por = usuario
    lancamento.motivo_cancelamento = motivo
    lancamento.save()
    return lancamento


# --- Closing the books (decision 096) -------------------------------------------------


def fechado_ate(clinica_id):
    """Last day of the clinic's closed period, or None. Explicit clinic: also called by
    commands that run without the request's isolation."""
    ultimo = Fechamento.todos.filter(clinica_id=clinica_id).first()  # newest first
    return ultimo.ate if ultimo else None


def conferir_periodo(clinica_id, data):
    """Refuse money dated inside the closed period. Locks the clinic row, shared with
    fechar(), so a payment cannot slip in while the period is being closed."""
    Clinica.objects.select_for_update().get(pk=clinica_id)
    ate = fechado_ate(clinica_id)
    if ate is not None and data <= ate:
        raise ValidationError(
            _(
                "O financeiro está fechado até %(ate)s: pagamentos e estornos nessa data ou "
                "antes dela não podem ser registrados. Use uma data posterior ou peça ao "
                "administrador para reabrir o período."
            )
            % {"ate": date_format(ate, "SHORT_DATE_FORMAT")}
        )


@transaction.atomic
def fechar(clinica, ate, *, usuario):
    """Close the books up to `ate` (at most yesterday: today's cash is still moving)."""
    Clinica.objects.select_for_update().get(pk=clinica.pk)
    if ate >= timezone.localdate():
        raise ValidationError(_("Feche no máximo até ontem: hoje ainda há movimento."))
    atual = fechado_ate(clinica.pk)
    if atual is not None and ate <= atual:
        raise ValidationError(
            _("O financeiro já está fechado até %(ate)s. Para voltar, reabra o período.")
            % {"ate": date_format(atual, "SHORT_DATE_FORMAT")}
        )
    return Fechamento.objects.create(clinica=clinica, ate=ate, criado_por=usuario)


@transaction.atomic
def reabrir(clinica, ate, *, motivo, usuario):
    """Move the closing back to `ate` (None opens everything). A reason is required."""
    Clinica.objects.select_for_update().get(pk=clinica.pk)
    atual = fechado_ate(clinica.pk)
    if atual is None:
        raise ValidationError(_("O financeiro não está fechado."))
    if ate is not None and ate >= atual:
        raise ValidationError(_("Para reabrir, escolha uma data anterior ao fechamento atual."))
    if not motivo.strip():
        raise ValidationError(_("Informe o motivo da reabertura."))
    return Fechamento.objects.create(
        clinica=clinica, ate=ate, motivo=motivo.strip(), criado_por=usuario
    )


def situacao(parcela, hoje=None):
    """Status of an installment annotated with com_saldo() (code, label)."""
    hoje = hoje or timezone.localdate()
    if parcela.lancamento.cancelado:
        return "cancelada", _("Cancelada")
    if parcela.saldo <= 0:
        return "paga", _("Paga")
    if parcela.vencimento < hoje:
        return "vencida", _("Vencida")
    if parcela.pago > 0:
        return "parcial", _("Paga em parte")
    return "aberta", _("Em aberto")


def devedores(hoje=None):
    """Who owes the clinic, from the open installments of receivables.

    One row per patient (or payer name): overdue total split by days late, amount not yet
    due and the oldest due date, ordered by the overdue total.
    """
    hoje = hoje or timezone.localdate()
    parcelas = (
        Parcela.objects.abertas()
        .filter(lancamento__tipo=Lancamento.Tipo.RECEBER)
        .select_related("lancamento__paciente")
    )
    linhas = defaultdict(
        lambda: {
            "paciente": None,
            "nome": "",
            "faixas": [ZERO] * (len(FAIXAS_DE_ATRASO) + 1),
            "vencido": ZERO,
            "a_vencer": ZERO,
            "mais_antigo": None,
        }
    )
    for parcela in parcelas:
        lancamento = parcela.lancamento
        chave = (
            ("paciente", lancamento.paciente_id)
            if lancamento.paciente_id
            else (
                "pessoa",
                lancamento.pessoa.strip().lower(),
            )
        )
        linha = linhas[chave]
        linha["paciente"] = lancamento.paciente
        linha["nome"] = lancamento.nome_pessoa
        if parcela.vencimento >= hoje:
            linha["a_vencer"] += parcela.saldo
            continue
        atraso = (hoje - parcela.vencimento).days
        faixa = next(
            (i for i, limite in enumerate(FAIXAS_DE_ATRASO) if atraso <= limite),
            len(FAIXAS_DE_ATRASO),
        )
        linha["faixas"][faixa] += parcela.saldo
        linha["vencido"] += parcela.saldo
        if linha["mais_antigo"] is None or parcela.vencimento < linha["mais_antigo"]:
            linha["mais_antigo"] = parcela.vencimento
    resultado = [linha for linha in linhas.values() if linha["vencido"] or linha["a_vencer"]]
    return sorted(resultado, key=lambda linha: (-linha["vencido"], chave_alfabetica(linha["nome"])))


def resumo_do_paciente(paciente, hoje=None):
    """Open installments, totals and latest payments of a patient (for the record)."""
    hoje = hoje or timezone.localdate()
    abertas = list(
        Parcela.objects.abertas()
        .filter(lancamento__paciente=paciente, lancamento__tipo=Lancamento.Tipo.RECEBER)
        .select_related("lancamento")
        .order_by("vencimento")
    )
    return {
        "abertas": abertas,
        "vencido": sum((p.saldo for p in abertas if p.vencimento < hoje), start=ZERO),
        "a_vencer": sum((p.saldo for p in abertas if p.vencimento >= hoje), start=ZERO),
        "pagamentos": list(
            Pagamento.objects.filter(parcela__lancamento__paciente=paciente)
            .select_related("parcela__lancamento", "conta")
            .order_by("-data", "-pk")[:5]
        ),
    }


# --- Cash flow and reports (0.16.0) ------------------------------------------------------


def _sinal(tipo):
    """Receivables bring money in (+), payables take it out (-)."""
    return 1 if tipo == Lancamento.Tipo.RECEBER else -1


def pagamentos_validos():
    return Pagamento.objects.filter(estornado=False, parcela__lancamento__cancelado=False)


def saldos_das_contas(ate=None):
    """[(account, balance)] = initial balance + money in - money out (payments up to `ate`).

    Summed in the database, grouped by account, so it does not grow with the history.
    """
    from .models import Conta

    pagamentos = pagamentos_validos()
    if ate is not None:
        pagamentos = pagamentos.filter(data__lte=ate)
    movimento = defaultdict(lambda: ZERO)
    for conta_id, tipo, total in (
        pagamentos.order_by()
        .values_list("conta_id", "parcela__lancamento__tipo")
        .annotate(total=Sum("valor"))
    ):
        movimento[conta_id] += _sinal(tipo) * total
    movimentos = MovimentoCaixa.objects.all()
    if ate is not None:
        movimentos = movimentos.filter(criado_em__date__lte=ate)
    for conta_id, outra_id, tipo, total in (
        movimentos.order_by()
        .values_list("caixa__conta_id", "outra_conta_id", "tipo")
        .annotate(total=Sum("valor"))
    ):
        # A withdrawal leaves the drawer (into the other account, if any); a top-up enters it.
        sinal = -1 if tipo == MovimentoCaixa.Tipo.RETIRADA else 1
        movimento[conta_id] += sinal * total
        if outra_id:
            movimento[outra_id] -= sinal * total
    return [
        (conta, conta.saldo_inicial + movimento[conta.pk])
        for conta in Conta.objects.all().order_by("nome")
    ]


def fluxo_de_caixa(de, ate, por_mes=False, hoje=None):
    """Rows per day (or month) from `de` to `ate`.

    Actual = payments made (by payment date); expected = what is still open in the
    installments due in the period (overdue ones included, flagged by the date). The
    running balance starts from the accounts' balance on the day before `de` and adds both.
    """
    hoje = hoje or timezone.localdate()

    def chave(data):
        return data.replace(day=1) if por_mes else data

    linhas = defaultdict(
        lambda: {
            "entradas": ZERO,
            "saidas": ZERO,
            "entradas_previstas": ZERO,
            "saidas_previstas": ZERO,
        }
    )
    for data, tipo, valor in (
        pagamentos_validos()
        .filter(data__gte=de, data__lte=ate)
        .values_list("data", "parcela__lancamento__tipo", "valor")
    ):
        linhas[chave(data)]["entradas" if tipo == Lancamento.Tipo.RECEBER else "saidas"] += valor
    # Drawer movements to or from outside the system (moves between accounts net to zero).
    for momento, tipo, valor in MovimentoCaixa.objects.filter(
        outra_conta__isnull=True, criado_em__date__gte=de, criado_em__date__lte=ate
    ).values_list("criado_em", "tipo", "valor"):
        data = timezone.localtime(momento).date()
        linhas[chave(data)]["saidas" if tipo == MovimentoCaixa.Tipo.RETIRADA else "entradas"] += (
            valor
        )
    for parcela in (
        Parcela.objects.abertas()
        .filter(vencimento__gte=de, vencimento__lte=ate)
        .select_related("lancamento")
    ):
        campo = (
            "entradas_previstas"
            if parcela.lancamento.tipo == Lancamento.Tipo.RECEBER
            else "saidas_previstas"
        )
        linhas[chave(parcela.vencimento)][campo] += parcela.saldo

    anterior = de - datetime.timedelta(days=1)
    saldo_inicial = sum((valor for _conta, valor in saldos_das_contas(ate=anterior)), start=ZERO)
    saldo = saldo_inicial
    resultado = []
    for data in sorted(linhas):
        linha = linhas[data]
        linha["data"] = data
        linha["atrasado"] = (
            not por_mes
            and data < hoje
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


def recebido_e_pago(de, ate):
    """(money received, money paid) from `de` to `ate`, in one query (home page, 0.24.0)."""
    totais = dict(
        pagamentos_validos()
        .filter(data__gte=de, data__lte=ate)
        .order_by()
        .values_list("parcela__lancamento__tipo")
        .annotate(total=Sum("valor"))
    )
    return totais.get(Lancamento.Tipo.RECEBER, ZERO), totais.get(Lancamento.Tipo.PAGAR, ZERO)


def relatorio(de, ate):
    """Money received and paid in the period, grouped for the reports page."""
    pagamentos = pagamentos_validos().filter(data__gte=de, data__lte=ate)
    recebidos = pagamentos.filter(parcela__lancamento__tipo=Lancamento.Tipo.RECEBER)
    pagos = pagamentos.filter(parcela__lancamento__tipo=Lancamento.Tipo.PAGAR)

    def agrupar(consulta, campo, rotulo=None):
        grupos = consulta.order_by().values_list(campo).annotate(total=Sum("valor"))
        linhas = [((rotulo or {}).get(chave, chave), total) for chave, total in grupos]
        return sorted(linhas, key=lambda linha: -linha[1])

    def somar(consulta, campo):
        return consulta.aggregate(total=Coalesce(Sum(campo), ZERO, output_field=DINHEIRO))["total"]

    formas = dict(Pagamento.Forma.choices)
    total_recebido = somar(recebidos, "valor")
    total_pago = somar(pagos, "valor")
    # The chart of accounts (decision 097) only once the clinic has groups.
    grupos = GrupoContabil.objects.exists()
    # Cost centers (decision 095) only once the clinic has registered one.
    centros = CentroCusto.objects.exists()
    sem_centro = {None: _("Sem centro de custo")}
    centro = "parcela__lancamento__centro_custo__nome"
    return {
        "grupos": grupos,
        "por_grupo": arvore_por_grupo(recebidos, Categoria.Tipo.RECEITA) if grupos else [],
        "despesas_por_grupo": arvore_por_grupo(pagos, Categoria.Tipo.DESPESA) if grupos else [],
        "centros": centros,
        "por_centro": agrupar(recebidos, centro, sem_centro) if centros else [],
        "despesas_por_centro": agrupar(pagos, centro, sem_centro) if centros else [],
        "por_forma": agrupar(recebidos, "forma", formas),
        "por_categoria": agrupar(recebidos, "parcela__lancamento__categoria__nome"),
        "por_profissional": agrupar(recebidos, "parcela__lancamento__profissional__nome"),
        "despesas_por_categoria": agrupar(pagos, "parcela__lancamento__categoria__nome"),
        "total_recebido": total_recebido,
        "total_pago": total_pago,
        "resultado": total_recebido - total_pago,
        "descontos": somar(recebidos, "desconto"),
        "juros": somar(recebidos, "juros"),
    }


def ligar_grupos(consulta):
    """The groups with each parent set from the same list, so numbers like 2.1 are
    built without one query per level."""
    grupos = list(consulta)
    por_id = {grupo.pk: grupo for grupo in grupos}
    for grupo in grupos:
        if grupo.pai_id in por_id:
            grupo.pai = por_id[grupo.pai_id]
    return grupos


def em_ordem_de_arvore(grupos):
    """(level, group) pairs in chart order: each group followed by its subgroups."""
    filhos = defaultdict(list)
    for grupo in grupos:  # already in chart order (code, then name)
        filhos[grupo.pai_id].append(grupo)
    saida = []

    def descer(pai_id, nivel):
        for grupo in filhos[pai_id]:
            saida.append((nivel, grupo))
            descer(grupo.pk, nivel + 1)

    descer(None, 0)
    return saida


def totais_por_grupo(pagamentos, tipo):
    """Payments summed by group, each group including its subgroups.

    Returns (groups of the type, {group id: total}, total of categories outside any group).
    """
    por_categoria = dict(
        pagamentos.order_by()
        .values_list("parcela__lancamento__categoria_id")
        .annotate(total=Sum("valor"))
    )
    grupo_da_categoria = dict(Categoria.objects.filter(tipo=tipo).values_list("pk", "grupo_id"))
    grupos = ligar_grupos(GrupoContabil.objects.filter(tipo=tipo))
    pai = {grupo.pk: grupo.pai_id for grupo in grupos}
    totais = defaultdict(lambda: ZERO)
    sem_grupo = ZERO
    for categoria_id, valor in por_categoria.items():
        grupo_id = grupo_da_categoria.get(categoria_id)
        if grupo_id is None:
            sem_grupo += valor
        while grupo_id is not None:
            totais[grupo_id] += valor
            grupo_id = pai.get(grupo_id)
    return grupos, totais, sem_grupo


def arvore_por_grupo(pagamentos, tipo):
    """(level, name, total) rows in tree order for the reports, groups without money left
    out, and a last row for the categories outside any group."""
    grupos, totais, sem_grupo = totais_por_grupo(pagamentos, tipo)
    linhas = [
        (nivel, str(grupo), totais[grupo.pk])
        for nivel, grupo in em_ordem_de_arvore(grupos)
        if totais[grupo.pk]
    ]
    if sem_grupo:
        linhas.append((0, _("Sem grupo"), sem_grupo))
    return linhas


# --- Yearly planning (decision 098) ---------------------------------------------------


def fracao_do_ano(ano, hoje=None):
    """Share of the year already gone: 0 before it starts, 1 once it is over."""
    hoje = hoje or timezone.localdate()
    inicio, fim = datetime.date(ano, 1, 1), datetime.date(ano, 12, 31)
    if hoje < inicio:
        return Decimal(0)
    if hoje >= fim:
        return Decimal(1)
    return Decimal((hoje - inicio).days + 1) / Decimal((fim - inicio).days + 1)


def planejamento(ano, hoje=None):
    """Goals of the year next to what was received and paid, group by group.

    "Esperado" is the goal times the share of the year gone, so mid-year a group can be
    compared with where it should be. Section totals add the goals of the highest groups
    that have one, so a goal and its subgroups' goals are not counted twice.
    """
    fracao = fracao_do_ano(ano, hoje)
    metas = dict(Planejamento.objects.filter(ano=ano).values_list("grupo_id", "valor"))
    pagamentos = pagamentos_validos().filter(data__year=ano)
    secoes = []
    for tipo, rotulo, lancamentos in (
        (Categoria.Tipo.RECEITA, _("Receitas"), Lancamento.Tipo.RECEBER),
        (Categoria.Tipo.DESPESA, _("Despesas"), Lancamento.Tipo.PAGAR),
    ):
        grupos, totais, sem_grupo = totais_por_grupo(
            pagamentos.filter(parcela__lancamento__tipo=lancamentos), tipo
        )
        linhas, meta_total, cobertos = [], ZERO, set()
        for nivel, grupo in em_ordem_de_arvore(grupos):
            meta, realizado = metas.get(grupo.pk), totais[grupo.pk]
            if not grupo.ativo and meta is None and not realizado:
                continue
            if meta and grupo.pai_id not in cobertos:
                meta_total += meta
            if meta or grupo.pai_id in cobertos:
                cobertos.add(grupo.pk)
            esperado = (meta * fracao).quantize(CENTAVO) if meta else None
            linhas.append(
                {
                    "nivel": nivel,
                    "grupo": grupo,
                    "meta": meta,
                    "realizado": realizado,
                    "esperado": esperado,
                    "percentual": round(100 * realizado / meta) if meta else None,
                    # On track: income at or above where it should be, expenses at or below.
                    "em_dia": None
                    if not meta
                    else realizado >= esperado
                    if tipo == Categoria.Tipo.RECEITA
                    else realizado <= esperado,
                }
            )
        realizado_total = sum((totais[g.pk] for g in grupos if g.pai_id is None), ZERO) + sem_grupo
        secoes.append(
            {
                "tipo": tipo,
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
    for grupo, valor in valores.items():
        if valor:
            Planejamento.objects.update_or_create(ano=ano, grupo=grupo, defaults={"valor": valor})
        else:
            Planejamento.objects.filter(ano=ano, grupo=grupo).delete()


@transaction.atomic
def copiar_metas(ano):
    """Copy last year's goals into the groups still without a goal; returns how many."""
    existentes = set(Planejamento.objects.filter(ano=ano).values_list("grupo_id", flat=True))
    copiadas = 0
    for anterior in Planejamento.objects.filter(ano=ano - 1).exclude(grupo_id__in=existentes):
        # One by one, not bulk_create, so the audit log records each goal.
        Planejamento.objects.create(ano=ano, grupo_id=anterior.grupo_id, valor=anterior.valor)
        copiadas += 1
    return copiadas


# --- Daily cash drawer (0.17.0) ----------------------------------------------------------


def caixa_aberto(conta):
    return Caixa.objects.filter(conta=conta, fechado_em__isnull=True).first()


@transaction.atomic
def abrir_caixa(conta, *, valor, usuario):
    if caixa_aberto(conta) is not None:
        raise ValidationError(_("O caixa desta conta já está aberto."))
    return Caixa.objects.create(
        clinica=conta.clinica, conta=conta, valor_abertura=valor, aberto_por=usuario
    )


def resumo_do_caixa(caixa):
    """Money that went through the drawer since it was opened, and the expected amount.

    Payments count by the moment they were registered (not their date), so a payment
    typed in today for last week still lands in today's drawer.
    """
    fim = caixa.fechado_em or timezone.now()
    pagamentos = list(
        pagamentos_validos()
        .filter(conta=caixa.conta, criado_em__gte=caixa.aberto_em, criado_em__lte=fim)
        .select_related("parcela__lancamento__paciente")
        .order_by("criado_em")
    )
    movimentos = list(caixa.movimentos.select_related("outra_conta", "criado_por"))
    entradas = sum(
        (p.valor for p in pagamentos if p.parcela.lancamento.tipo == Lancamento.Tipo.RECEBER),
        start=ZERO,
    )
    saidas = sum(
        (p.valor for p in pagamentos if p.parcela.lancamento.tipo == Lancamento.Tipo.PAGAR),
        start=ZERO,
    )
    reforcos = sum(
        (m.valor for m in movimentos if m.tipo == MovimentoCaixa.Tipo.REFORCO), start=ZERO
    )
    retiradas = sum(
        (m.valor for m in movimentos if m.tipo == MovimentoCaixa.Tipo.RETIRADA), start=ZERO
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
def movimentar_caixa(caixa, *, tipo, valor, motivo, usuario, outra_conta=None):
    caixa = Caixa.objects.select_for_update().get(pk=caixa.pk)
    if not caixa.aberto:
        raise ValidationError(_("Este caixa já foi fechado."))
    if outra_conta is not None and outra_conta.pk == caixa.conta_id:
        raise ValidationError(_("Escolha uma conta diferente da do caixa."))
    if tipo == MovimentoCaixa.Tipo.RETIRADA and valor > resumo_do_caixa(caixa)["esperado"]:
        raise ValidationError(_("A retirada passa do valor que deveria estar no caixa."))
    return MovimentoCaixa.objects.create(
        clinica=caixa.clinica,
        caixa=caixa,
        tipo=tipo,
        valor=valor,
        motivo=motivo,
        outra_conta=outra_conta,
        criado_por=usuario,
    )


@transaction.atomic
def fechar_caixa(caixa, *, valor_contado, observacao, usuario):
    caixa = Caixa.objects.select_for_update().get(pk=caixa.pk)
    if not caixa.aberto:
        raise ValidationError(_("Este caixa já foi fechado."))
    caixa.valor_esperado = resumo_do_caixa(caixa)["esperado"]
    caixa.valor_contado = valor_contado
    caixa.observacao = observacao
    caixa.fechado_em = timezone.now()
    caixa.fechado_por = usuario
    caixa.save()
    return caixa
