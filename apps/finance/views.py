"""Finance: receivables (0.15.0), payables, cash flow and reports (0.16.0), commission (0.19.0),
bank statement import (0.20.0).

Receivables belong to the Recebimentos module (administrators and the front desk, which
cannot cancel, reverse or discount). Payables, accounts, categories, cash flow and reports
belong to the Financeiro module (administrators). Entries and payments of both kinds share
the same screens; each view checks the module of the entry's kind.
"""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from apps.core import legislation
from apps.core.ordering import chave_alfabetica
from apps.core.permissions import Acao, Modulo, exige_permissao, pode
from apps.core.templatetags.formats import currency
from apps.core.validators import normalizar_cnpj
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import commissions, reconciliation, services
from .forms import (
    AbrirCaixaForm,
    CategoriaForm,
    CentroCustoForm,
    ContaForm,
    FecharCaixaForm,
    FecharForm,
    FornecedorForm,
    GrupoContabilForm,
    ImportarExtratoForm,
    LancamentoDaTransacaoForm,
    LancamentoPagarForm,
    LancamentoReceberForm,
    MotivoForm,
    MovimentoCaixaForm,
    PagarComissaoForm,
    PercentualComissaoForm,
    PlanejamentoForm,
    ReabrirForm,
    ReceberForm,
)
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
    FinancialAccount,
    Installment,
    Payment,
    Planning,
    StatementImport,
    Supplier,
)
from .ofx import ArquivoInvalido

POR_PAGINA = 50
SITUACOES = {
    "abertas": Q(balance__gt=0, entry__cancelled=False),
    "vencidas": Q(balance__gt=0, entry__cancelled=False),  # + due date before today
    "pagas": Q(balance__lte=0, entry__cancelled=False),
    "todas": Q(),
}


def _modulo(kind):
    return Modulo.RECEBIMENTOS if kind == Entry.Tipo.RECEBER else Modulo.FINANCEIRO


def _exigir(request, kind, acao):
    """Payables need the Financeiro module (administrators) for the same action."""
    if not pode(request, _modulo(kind), acao):
        raise PermissionDenied


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def receber_lista(request):
    return _lista(request, Entry.Tipo.RECEBER)


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def pagar_lista(request):
    return _lista(request, Entry.Tipo.PAGAR)


def _lista(request, kind):
    hoje = timezone.localdate()
    status = request.GET.get("status", "abertas")
    busca = request.GET.get("q", "").strip()
    parcelas = (
        Installment.objects.com_saldo()
        .filter(entry__kind=kind)
        .select_related("entry__patient", "entry")
        .filter(SITUACOES.get(status, SITUACOES["abertas"]))
    )
    if status == "vencidas":
        parcelas = parcelas.filter(due_date__lt=hoje)
    if busca:
        parcelas = parcelas.filter(
            Q(entry__patient__name__unaccent__icontains=busca)
            | Q(entry__payer__unaccent__icontains=busca)
            | Q(entry__description__unaccent__icontains=busca)
        )
    parcelas = parcelas.order_by("due_date", "pk")
    pagina = Paginator(parcelas, POR_PAGINA).get_page(request.GET.get("pagina"))
    for installment in pagina:
        installment.status = services.status(installment, hoje)
    return render(
        request,
        "finance/list.html",
        {
            "kind": kind,
            "pagar": kind == Entry.Tipo.PAGAR,
            "pagina": pagina,
            "status": status,
            "busca": busca,
            "parametros": urlencode({"status": status, "q": busca}),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def lancamento_novo(request):
    inicial = {}
    code = request.GET.get("patient", "")
    patient = None
    if code.isdecimal():
        patient = Patient.objects.filter(pk=int(code), archived=False).first()
        if patient is not None:
            inicial["patient"] = patient.pk
    form = LancamentoReceberForm(request.POST or None, initial=inicial, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        entry = services.criar_lancamento(
            clinic=request.clinic,
            kind=Entry.Tipo.RECEBER,
            patient=dados["patient"],
            payer="" if dados["patient"] else dados["payer"].strip(),
            description=dados["description"],
            category=dados["category"],
            cost_center=dados.get("cost_center"),
            practitioner=dados["practitioner"],
            notes=dados["notes"],
            total_amount=dados["total_amount"],
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            user=request.user,
        )
        if dados["recebido_agora"]:
            primeira = entry.parcelas.order_by("number").first()
            payment = services.receber(
                primeira,
                user=request.user,
                amount=primeira.amount,
                method=dados["method"],
                account=dados["account"],
            )
            messages.success(request, _("Lançamento criado e 1ª parcela recebida."))
            return redirect("finance:receipt", pk=payment.pk)
        messages.success(request, _("Lançamento criado."))
        return redirect("finance:entry", pk=entry.pk)
    if patient is None and form["patient"].value():
        patient = Patient.objects.filter(pk=form["patient"].value()).first()
    return render(request, "finance/entry_form.html", {"form": form, "patient": patient})


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def despesa_nova(request):
    form = LancamentoPagarForm(
        request.POST or None,
        clinic=request.clinic,
        initial={"supplier": request.GET.get("supplier")},
    )
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        entry = services.criar_lancamento(
            clinic=request.clinic,
            kind=Entry.Tipo.PAGAR,
            supplier=dados["supplier"],
            payer=dados["payer"].strip(),
            description=dados["description"],
            category=dados["category"],
            cost_center=dados.get("cost_center"),
            notes=dados["notes"],
            total_amount=form.total_amount(),
            parcelas=dados["parcelas"],
            primeiro_vencimento=dados["primeiro_vencimento"],
            user=request.user,
        )
        if dados["pago_agora"]:
            primeira = entry.parcelas.order_by("number").first()
            services.receber(
                primeira,
                user=request.user,
                amount=primeira.amount,
                method=dados["method"],
                account=dados["account"],
            )
        messages.success(request, _("Despesa lançada."))
        return redirect("finance:entry", pk=entry.pk)
    return render(request, "finance/expense_form.html", {"form": form})


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def entry(request, pk):
    entry = get_object_or_404(
        Entry.objects.select_related("patient", "category", "cost_center", "practitioner"),
        pk=pk,
    )
    _exigir(request, entry.kind, Acao.VER)
    hoje = timezone.localdate()
    parcelas = list(Installment.objects.com_saldo().filter(entry=entry).select_related("entry"))
    pagamentos = Payment.objects.filter(installment__entry=entry).select_related(
        "installment", "account", "created_by"
    )
    for installment in parcelas:
        installment.status = services.status(installment, hoje)
        installment.lista_pagamentos = [p for p in pagamentos if p.installment_id == installment.pk]
    return render(
        request,
        "finance/entry.html",
        {
            "entry": entry,
            "pagar": entry.kind == Entry.Tipo.PAGAR,
            "pode_alterar": pode(request, _modulo(entry.kind), Acao.CRIAR),
            "pode_excluir": pode(request, _modulo(entry.kind), Acao.EXCLUIR),
            "parcelas": parcelas,
            "total_pago": sum(p.pago for p in parcelas),
            "total_saldo": sum(p.balance for p in parcelas) if not entry.cancelled else 0,
            "commission": Commission.objects.filter(entry=entry).first(),
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def lancamento_cancelar(request, pk):
    entry = get_object_or_404(Entry.objects, pk=pk, cancelled=False)
    _exigir(request, entry.kind, Acao.EXCLUIR)
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.cancelar(entry, reason=form.cleaned_data["reason"], user=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento cancelado."))
        return redirect("finance:entry", pk=entry.pk)
    return render(
        request,
        "finance/reason.html",
        {
            "form": form,
            "titulo": _("Cancelar lançamento"),
            "objeto": entry,
            "voltar": entry.pk,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def receber(request, pk):
    installment = get_object_or_404(
        Installment.objects.com_saldo().select_related("entry__patient"),
        pk=pk,
        entry__cancelled=False,
    )
    _exigir(request, installment.entry.kind, Acao.CRIAR)
    pagar = installment.entry.kind == Entry.Tipo.PAGAR
    if installment.balance <= 0:
        messages.info(request, _("Esta parcela já está paga."))
        return redirect("finance:entry", pk=installment.entry_id)
    pode_desconto = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR)
    conta_padrao = FinancialAccount.objects.filter(
        active=True, kind=FinancialAccount.Tipo.DINHEIRO
    ).first()
    form = ReceberForm(
        request.POST or None,
        initial={
            "amount": installment.balance,
            "date": timezone.localdate(),
            "account": conta_padrao,
        },
        pode_dar_desconto=pode_desconto,
    )
    if pagar:
        form.fields["amount"].label = _("Valor pago")
        form.fields["interest"].help_text = _("Já incluídos no valor pago.")
    if request.method == "POST" and form.is_valid():
        dados = {campo: value for campo, value in form.cleaned_data.items() if campo in form.fields}
        dados.setdefault("discount", 0)
        dados["interest"] = dados.get("interest") or 0
        try:
            payment = services.receber(installment, user=request.user, **dados)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Pagamento registrado."))
            if pagar:
                return redirect("finance:entry", pk=installment.entry_id)
            return redirect("finance:receipt", pk=payment.pk)
    return render(
        request,
        "finance/receive.html",
        {
            "form": form,
            "installment": installment,
            "total_parcelas": installment.entry.parcelas.count(),
            "pode_desconto": pode_desconto,
            "pagar": pagar,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def recibo(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related(
            "installment__entry__patient",
            "installment__entry__practitioner",
            "account",
            "created_by",
        ),
        pk=pk,
        installment__entry__kind=Entry.Tipo.RECEBER,
    )
    return render(
        request,
        "finance/receipt.html",
        {
            "payment": payment,
            "entry": payment.installment.entry,
            "total_parcelas": payment.installment.entry.parcelas.count(),
            # Where a tax document is required, the receipt says it does not replace it.
            "documento_fiscal": legislation.do_pais().fiscal,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.EXCLUIR)
def estornar(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("installment__entry"), pk=pk, reversed=False
    )
    _exigir(request, payment.installment.entry.kind, Acao.EXCLUIR)
    form = MotivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.estornar(payment, reason=form.cleaned_data["reason"], user=request.user)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Pagamento estornado."))
        return redirect("finance:entry", pk=payment.installment.entry_id)
    return render(
        request,
        "finance/reason.html",
        {
            "form": form,
            "titulo": _("Estornar pagamento"),
            # Not str(pagamento): that has the raw amount ("1350.00"), for the audit log.
            "objeto": " · ".join(
                [
                    str(payment.installment),
                    currency(payment.amount),
                    date_format(payment.date, "SHORT_DATE_FORMAT"),
                ]
            ),
            "voltar": payment.installment.entry_id,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def devedores(request):
    linhas = services.devedores()
    busca = request.GET.get("q", "").strip()
    encontrados = linhas
    if busca:
        termo = chave_alfabetica(busca)
        encontrados = [linha for linha in linhas if termo in chave_alfabetica(linha["name"])]
    # A clinic with years of use has thousands of debtors: one page held them all (volume
    # test, decision 108). The totals still add up everyone.
    pagina = Paginator(encontrados, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/debtors.html",
        {
            "pagina": pagina,
            "busca": busca,
            "parametros": urlencode({"q": busca}),
            "total_vencido": sum(linha["vencido"] for linha in linhas),
            "total_a_vencer": sum(linha["a_vencer"] for linha in linhas),
        },
    )


# --- Daily cash drawer (0.17.0) ---------------------------------------------------------


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def cash_register(request):
    """The drawer of a cash account: its open session, or the form to open it."""
    contas = list(FinancialAccount.objects.filter(kind=FinancialAccount.Tipo.DINHEIRO, active=True))
    escolhida = request.GET.get("account", "")
    account = next((c for c in contas if str(c.pk) == escolhida), contas[0] if contas else None)
    if account is not None:
        aberto = services.caixa_aberto(account)
        if aberto is not None:
            return redirect("finance:cash_detail", pk=aberto.pk)
    balance = dict(services.saldos_das_contas()).get(account) if account else None
    # Empty on purpose: the opening amount is what is counted, not the system balance.
    form = AbrirCaixaForm(request.POST or None)
    if request.method == "POST" and account is not None:
        if not pode(request, Modulo.RECEBIMENTOS, Acao.CRIAR):
            raise PermissionDenied
        if form.is_valid():
            try:
                novo = services.abrir_caixa(
                    account, amount=form.cleaned_data["amount"], user=request.user
                )
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
                return redirect(f"{request.path}?account={account.pk}")
            messages.success(request, _("Caixa aberto."))
            return redirect("finance:cash_detail", pk=novo.pk)
    historico = CashRegister.objects.filter(account=account).select_related(
        "opened_by", "closed_by"
    )[:30]
    return render(
        request,
        "finance/cash.html",
        {
            "contas": contas,
            "account": account,
            "form": form,
            "saldo_sistema": balance,
            "historico": historico,
        },
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.VER)
def caixa_detalhe(request, pk):
    sessao = get_object_or_404(
        CashRegister.objects.select_related("account", "opened_by", "closed_by"), pk=pk
    )
    return render(
        request,
        "finance/cash_detail.html",
        {"cash_register": sessao, "resumo": services.resumo_do_caixa(sessao)},
    )


# The kind of cash movement in the URL (decision 155) and the value the database stores.
MOVIMENTOS_NA_URL = {
    "withdrawal": CashMovement.Tipo.RETIRADA,
    "top-up": CashMovement.Tipo.REFORCO,
}


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_movimento(request, pk, kind):
    sessao = get_object_or_404(
        CashRegister.objects.select_related("account"), pk=pk, closed_at=None
    )
    if kind not in MOVIMENTOS_NA_URL:
        raise Http404
    kind = MOVIMENTOS_NA_URL[kind]
    form = MovimentoCaixaForm(request.POST or None, cash_register=sessao)
    if request.method == "POST" and form.is_valid():
        try:
            services.movimentar_caixa(sessao, kind=kind, user=request.user, **form.cleaned_data)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            messages.success(request, _("Movimento registrado."))
            return redirect("finance:cash_detail", pk=sessao.pk)
    return render(
        request,
        "finance/cash_form.html",
        {"cash_register": sessao, "form": form, "titulo": CashMovement.Tipo(kind).label},
    )


@exige_permissao(Modulo.RECEBIMENTOS, Acao.CRIAR)
def caixa_fechar(request, pk):
    sessao = get_object_or_404(
        CashRegister.objects.select_related("account"), pk=pk, closed_at=None
    )
    form = FecharCaixaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.fechar_caixa(sessao, user=request.user, **form.cleaned_data)
        messages.success(request, _("Caixa fechado."))
        return redirect("finance:cash_detail", pk=sessao.pk)
    return render(
        request,
        "finance/cash_form.html",
        {
            "cash_register": sessao,
            "form": form,
            "titulo": _("Fechar caixa"),
            "esperado": services.resumo_do_caixa(sessao)["esperado"],
        },
    )


# --- Cash flow and reports (administrators) ---------------------------------------------


def _periodo(request):
    """(de, ate) from the query string; the current month by default (at most 2 years)."""
    hoje = timezone.localdate()
    inicio_do_mes = hoje.replace(day=1)
    fim_do_mes = services.somar_meses(inicio_do_mes, 1) - datetime.timedelta(days=1)
    try:
        de = datetime.date.fromisoformat(request.GET.get("de", ""))
    except ValueError:
        de = inicio_do_mes
    try:
        until = datetime.date.fromisoformat(request.GET.get("until", ""))
    except ValueError:
        until = fim_do_mes
    if until < de or (until - de).days > 731:
        de, until = inicio_do_mes, fim_do_mes
    return de, until


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fluxo_de_caixa(request):
    de, until = _periodo(request)
    por_mes = request.GET.get("agrupar") == "mes"
    return render(
        request,
        "finance/cash_flow.html",
        {
            "de": de,
            "until": until,
            "por_mes": por_mes,
            "fluxo": services.fluxo_de_caixa(de, until, por_mes=por_mes),
            "contas": services.saldos_das_contas(),
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def relatorios(request):
    de, until = _periodo(request)
    return render(
        request,
        "finance/reports.html",
        {
            "de": de,
            "until": until,
            "relatorio": services.relatorio(de, until),
            "fechado_ate": services.fechado_ate(request.clinic.pk),
        },
    )


# --- Yearly planning (decision 098) ---------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def planejamento(request):
    """Goals of the year per group of the chart of accounts, next to what was done."""
    hoje = timezone.localdate()
    try:
        year = int(request.GET.get("year", hoje.year))
    except ValueError:
        year = hoje.year
    year = min(max(year, 2000), hoje.year + 5)
    pode_alterar = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR)
    grupos = services.ligar_grupos(AccountGroup.objects.filter(active=True))
    metas = dict(Planning.objects.filter(year=year).values_list("group_id", "amount"))
    form = PlanejamentoForm(request.POST or None, grupos=grupos, metas=metas)
    if request.method == "POST":
        if not pode_alterar:
            raise PermissionDenied
        if request.POST.get("acao") == "copiar":
            copiadas = services.copiar_metas(year)
            messages.success(
                request,
                ngettext(
                    "%(n)s meta copiada do ano anterior.",
                    "%(n)s metas copiadas do ano anterior.",
                    copiadas,
                )
                % {"n": copiadas},
            )
            return redirect(f"{reverse('finance:planning')}?year={year}")
        if form.is_valid():
            services.salvar_metas(year, form.valores())
            messages.success(request, _("Planejamento salvo."))
            return redirect(f"{reverse('finance:planning')}?year={year}")
    dados = services.planejamento(year)
    for secao in dados["secoes"]:
        for linha in secao["linhas"]:
            if pode_alterar and linha["group"].active:
                linha["campo"] = form[PlanejamentoForm.name(linha["group"])]
    return render(
        request,
        "finance/planning.html",
        {
            **dados,
            "form": form,
            "pode_alterar": pode_alterar,
            "ano_anterior": year - 1,
            "proximo_ano": year + 1,
            "tem_metas_anteriores": Planning.objects.filter(year=year - 1).exists(),
        },
    )


# --- Closing the books (decision 096) -------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fechamento(request):
    """Close the books up to a date, or reopen them with a reason. Public demo logins only
    look: one visitor closing the books would block everyone else's payments."""
    demo = request.user.demo
    pode_fechar = pode(request, Modulo.FINANCEIRO, Acao.ALTERAR) and not demo
    pode_reabrir = pode(request, Modulo.FINANCEIRO, Acao.EXCLUIR) and not demo
    if request.method == "POST":
        acao = request.POST.get("acao")
        if not {"fechar": pode_fechar, "reabrir": pode_reabrir}.get(acao):
            raise PermissionDenied
        form = (FecharForm if acao == "fechar" else ReabrirForm)(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            try:
                if acao == "fechar":
                    services.fechar(request.clinic, dados["until"], user=request.user)
                    messages.success(request, _("Financeiro fechado."))
                else:
                    services.reabrir(
                        request.clinic, dados["until"], reason=dados["reason"], user=request.user
                    )
                    messages.success(request, _("Período reaberto."))
            except ValidationError as erro:
                messages.error(request, erro.messages[0])
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
        return redirect("finance:closing")
    return render(
        request,
        "finance/closing.html",
        {
            "fechado_ate": services.fechado_ate(request.clinic.pk),
            "historico": BookClosing.objects.select_related("created_by")[:30],
            "fechar_form": FecharForm() if pode_fechar else None,
            "reabrir_form": ReabrirForm() if pode_reabrir else None,
        },
    )


# --- Accounts, categories and cost centers (administrators) ----------------------------


CADASTROS = {
    "categories": (Category, CategoriaForm),
    "accounts": (FinancialAccount, ContaForm),
    "cost-centers": (CostCenter, CentroCustoForm),
}


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def cadastro_lista(request, cadastro):
    modelo, _form = CADASTROS[cadastro]
    return render(
        request,
        "finance/catalog_list.html",
        {"cadastro": cadastro, "itens": modelo.objects.all(), "modelo": modelo._meta},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def cadastro_form(request, cadastro, pk=None):
    modelo, classe = CADASTROS[cadastro]
    instancia = get_object_or_404(modelo.objects, pk=pk) if pk else modelo()
    form = classe(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": form.instance.name})
        return redirect("finance:catalog", cadastro=cadastro)
    return render(
        request,
        "finance/catalog_form.html",
        {"form": form, "cadastro": cadastro, "instancia": instancia, "modelo": modelo._meta},
    )


# --- Chart of accounts (decision 097) ---------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def plano_contas(request):
    """The chart of accounts as a tree: groups, subgroups and their categories."""
    grupos = services.ligar_grupos(AccountGroup.objects.all())
    categorias = list(Category.objects.all())
    arvores = []
    for kind, rotulo in Category.Tipo.choices:
        linhas = []

        def descer(parent_id, nivel, kind=kind, linhas=linhas):
            for group in (g for g in grupos if g.kind == kind and g.parent_id == parent_id):
                linhas.append({"nivel": nivel, "group": group})
                linhas.extend(
                    {"nivel": nivel + 1, "category": c}
                    for c in categorias
                    if c.group_id == group.pk
                )
                descer(group.pk, nivel + 1)

        descer(None, 0)
        sem_grupo = [c for c in categorias if c.kind == kind and c.group_id is None]
        arvores.append({"rotulo": rotulo, "linhas": linhas, "sem_grupo": sem_grupo})
    return render(request, "finance/chart_of_accounts.html", {"arvores": arvores})


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def grupo_novo(request):
    return _grupo_form(request, AccountGroup(kind=request.GET.get("kind") or None))


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def grupo_editar(request, pk):
    return _grupo_form(request, get_object_or_404(AccountGroup.objects, pk=pk))


def _grupo_form(request, instancia):
    form = GrupoContabilForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": group.name})
        return redirect("finance:chart_of_accounts")
    return render(request, "finance/group_form.html", {"form": form, "instancia": instancia})


# --- Suppliers (decision 093) ---------------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def fornecedores(request):
    busca = request.GET.get("q", "").strip()
    lista = Supplier.objects.all()
    if busca:
        filtro = Q(name__unaccent__icontains=busca) | Q(legal_name__unaccent__icontains=busca)
        document = normalizar_cnpj(busca)
        if any(c.isdigit() for c in document):
            filtro |= Q(tax_id__startswith=document)
        lista = lista.filter(filtro)
    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/suppliers.html",
        {"pagina": pagina, "busca": busca, "parametros": urlencode({"q": busca})},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def supplier(request, pk):
    supplier = get_object_or_404(Supplier.objects, pk=pk)
    hoje = timezone.localdate()
    parcelas = list(
        Installment.objects.com_saldo()
        .filter(entry__supplier=supplier)
        .select_related("entry")
        .order_by("-due_date", "-pk")[:POR_PAGINA]
    )
    for installment in parcelas:
        installment.status = services.status(installment, hoje)
    em_aberto = sum(
        (p.balance for p in Installment.objects.abertas().filter(entry__supplier=supplier)),
        start=ZERO,
    )
    return render(
        request,
        "finance/supplier.html",
        {"supplier": supplier, "parcelas": parcelas, "em_aberto": em_aberto},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def fornecedor_novo(request):
    return _fornecedor_form(request, Supplier())


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def fornecedor_editar(request, pk):
    return _fornecedor_form(request, get_object_or_404(Supplier.objects, pk=pk))


def _fornecedor_form(request, instancia):
    form = FornecedorForm(request.POST or None, instance=instancia, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": supplier.name})
        return redirect("finance:supplier", pk=supplier.pk)
    return render(request, "finance/supplier_form.html", {"form": form, "instancia": instancia})


# --- Practitioner commission (0.19.0) --------------------------------------------------


def _ate(request):
    hoje = timezone.localdate()
    try:
        return min(datetime.date.fromisoformat(request.GET.get("until", "")), hoje)
    except ValueError:
        return hoje


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def comissoes_lista(request):
    until = _ate(request)
    return render(
        request,
        "finance/commissions.html",
        {
            "until": until,
            "linhas": commissions.resumo(until),
            "sem_percentual": Practitioner.objects.filter(active=True, commission_percentage=0),
            "historico": Commission.objects.select_related("practitioner", "entry")[:30],
        },
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def commission_percentage(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    form = PercentualComissaoForm(request.POST or None, instance=practitioner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Percentual de %(nome)s salvo.") % {"nome": practitioner.name})
        return redirect("finance:commissions")
    return render(
        request,
        "finance/commission_percentage.html",
        {"form": form, "practitioner": practitioner},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def comissao_pagar(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    until = _ate(request)
    padrao = (
        Category.objects.filter(kind=Category.Tipo.DESPESA, name="Comissões", active=True).first()
        or Category.objects.filter(kind=Category.Tipo.DESPESA, active=True).first()
    )
    form = PagarComissaoForm(request.POST or None, initial={"category": padrao})
    if request.method == "POST" and form.is_valid():
        try:
            commission = commissions.pagar(
                practitioner, until=until, user=request.user, **form.cleaned_data
            )
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
            return redirect(f"{reverse('finance:commissions')}?until={until.isoformat()}")
        messages.success(request, _("Comissão lançada em A pagar."))
        return redirect("finance:entry", pk=commission.entry_id)
    return render(
        request,
        "finance/commission_pay.html",
        {"form": form, "calculo": commissions.pendente(practitioner, until), "until": until},
    )


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def commission(request, pk):
    commission = get_object_or_404(
        Commission.objects.select_related("practitioner", "entry"), pk=pk
    )
    pagamentos = commission.pagamentos.select_related("installment__entry__patient").order_by(
        "date", "pk"
    )
    reversal_deduction = commission.pagamentos_estornados.select_related(
        "installment__entry__patient", "commission"
    ).order_by("date", "pk")
    for estorno in reversal_deduction:
        estorno.comissao_devolvida = commissions.percentual_de(
            estorno.amount, estorno.commission.percentage
        )
    return render(
        request,
        "finance/commission.html",
        {
            "commission": commission,
            "pagamentos": pagamentos,
            "reversal_deduction": reversal_deduction,
        },
    )


# --- Bank statement (0.20.0) ------------------------------------------------------------


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def extratos(request):
    form = ImportarExtratoForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not pode(request, Modulo.FINANCEIRO, Acao.CRIAR):
            raise PermissionDenied
        if form.is_valid():
            file = form.cleaned_data["file"]
            try:
                statement_import = reconciliation.importar(
                    form.cleaned_data["account"],
                    nome_arquivo=file.name,
                    content=file.read(),
                    user=request.user,
                )
            except ArquivoInvalido as erro:
                form.add_error("file", str(erro))
            else:
                messages.success(
                    request,
                    _("Extrato importado: %(novas)s transações novas, %(repetidas)s já importadas.")
                    % {
                        "novas": statement_import.new_transactions,
                        "repetidas": statement_import.duplicate_transactions,
                    },
                )
                if statement_import.unreadable_transactions:
                    messages.warning(
                        request,
                        ngettext(
                            "%(n)s linha do arquivo não tinha data ou valor legível e não foi "
                            "importada. Confira no extrato do banco.",
                            "%(n)s linhas do arquivo não tinham data ou valor legível e não "
                            "foram importadas. Confira no extrato do banco.",
                            statement_import.unreadable_transactions,
                        )
                        % {"n": statement_import.unreadable_transactions},
                    )
                outra = reconciliation.outra_conta_no_banco(statement_import)
                if outra:
                    messages.warning(
                        request,
                        _(
                            "Atenção: este arquivo é da conta %(nova)s no banco, mas a anterior "
                            "importada em %(conta)s era da conta %(antiga)s."
                        )
                        % {
                            "nova": statement_import.bank_account_number,
                            "conta": statement_import.account,
                            "antiga": outra,
                        },
                    )
                return redirect("finance:statement", pk=statement_import.pk)
    importacoes = StatementImport.objects.select_related("account", "created_by")
    pendentes = dict(
        BankTransaction.objects.filter(status=BankTransaction.Situacao.PENDENTE)
        .values("statement_import")
        .annotate(n=Count("pk"))
        .values_list("statement_import", "n")
    )
    pagina = Paginator(importacoes, 30).get_page(request.GET.get("pagina"))
    for statement_import in pagina:
        statement_import.pendentes = pendentes.get(statement_import.pk, 0)
    return render(request, "finance/statements.html", {"form": form, "pagina": pagina})


@exige_permissao(Modulo.FINANCEIRO, Acao.VER)
def extrato(request, pk):
    statement_import = get_object_or_404(StatementImport.objects.select_related("account"), pk=pk)
    transacoes = list(
        statement_import.transacoes.select_related(
            "payment__installment__entry__patient", "cash_movement__cash_register__account"
        )
    )
    por_transacao = reconciliation.candidatos(transacoes)
    for transacao in transacoes:
        transacao.candidatos = por_transacao.get(transacao.pk, [])
    saldo_sistema = reconciliation.saldo_no_sistema(statement_import)
    return render(
        request,
        "finance/statement.html",
        {
            "statement_import": statement_import,
            "transacoes": transacoes,
            "pendentes": sum(t.status == BankTransaction.Situacao.PENDENTE for t in transacoes),
            "unicos": sum(len(t.candidatos) == 1 for t in transacoes),
            "saldo_sistema": saldo_sistema,
            "diferenca": statement_import.balance - saldo_sistema
            if saldo_sistema is not None
            else None,
        },
    )


def _voltar_ao_extrato(transacao):
    return redirect(
        f"{reverse('finance:statement', args=[transacao.statement_import_id])}#t{transacao.pk}"
    )


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def extrato_conciliar_unicos(request, pk):
    statement_import = get_object_or_404(StatementImport.objects, pk=pk)
    feitas = reconciliation.conciliar_unicos(statement_import, user=request.user)
    messages.success(request, _("%(n)s transações conciliadas.") % {"n": feitas})
    return redirect("finance:statement", pk=statement_import.pk)


@require_POST
@exige_permissao(Modulo.FINANCEIRO, Acao.ALTERAR)
def transacao_acao(request, pk, acao):
    transacao = get_object_or_404(BankTransaction.objects, pk=pk)
    try:
        if acao == "reconcile":
            reconciliation.conciliar(transacao, request.POST.get("chave", ""), user=request.user)
        elif acao == "ignore":
            reason = request.POST.get("reason", "").strip()[:200]
            if not reason:
                raise ValidationError(_("Informe o motivo para ignorar a transação."))
            reconciliation.ignorar(transacao, reason=reason, user=request.user)
        else:
            reconciliation.desfazer(transacao)
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
    return _voltar_ao_extrato(transacao)


@exige_permissao(Modulo.FINANCEIRO, Acao.CRIAR)
def transacao_lancamento(request, pk):
    transacao = get_object_or_404(BankTransaction.objects.select_related("account"), pk=pk)
    form = LancamentoDaTransacaoForm(
        request.POST or None,
        entrada=transacao.entrada,
        initial={"description": transacao.description},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reconciliation.criar_lancamento(transacao, user=request.user, **form.cleaned_data)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, _("Lançamento criado e conciliado."))
        return _voltar_ao_extrato(transacao)
    return render(request, "finance/transaction_entry.html", {"form": form, "transacao": transacao})
