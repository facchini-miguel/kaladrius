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
from apps.core.ordering import alphabetical_key
from apps.core.permissions import Action, Module, can, requires_permission
from apps.core.templatetags.formats import currency
from apps.core.validators import normalize_cnpj
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import commissions, reconciliation, services
from .forms import (
    AccountGroupForm,
    CashMovementForm,
    CategoryForm,
    CloseBooksForm,
    CloseCashRegisterForm,
    CommissionPercentageForm,
    CostCenterForm,
    FinancialAccountForm,
    ImportStatementForm,
    OpenCashRegisterForm,
    PayableEntryForm,
    PayCommissionForm,
    PlanningForm,
    ReasonForm,
    ReceivableEntryForm,
    ReceivePaymentForm,
    ReopenBooksForm,
    SupplierForm,
    TransactionEntryForm,
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
from .ofx import InvalidFile

PER_PAGE = 50
STATUSES = {
    "abertas": Q(balance__gt=0, entry__cancelled=False),
    "vencidas": Q(balance__gt=0, entry__cancelled=False),  # + due date before today
    "pagas": Q(balance__lte=0, entry__cancelled=False),
    "todas": Q(),
}


def _module(kind):
    return Module.RECEIVING if kind == Entry.Kind.RECEIVABLE else Module.FINANCE


def _require(request, kind, acao):
    """Payables need the Financeiro module (administrators) for the same action."""
    if not can(request, _module(kind), acao):
        raise PermissionDenied


@requires_permission(Module.RECEIVING, Action.VIEW)
def receivables(request):
    return _entry_list(request, Entry.Kind.RECEIVABLE)


@requires_permission(Module.FINANCE, Action.VIEW)
def payables(request):
    return _entry_list(request, Entry.Kind.PAYABLE)


def _entry_list(request, kind):
    today = timezone.localdate()
    status = request.GET.get("status", "abertas")
    search = request.GET.get("q", "").strip()
    parcelas = (
        Installment.objects.with_balance()
        .filter(entry__kind=kind)
        .select_related("entry__patient", "entry")
        .filter(STATUSES.get(status, STATUSES["abertas"]))
    )
    if status == "vencidas":
        parcelas = parcelas.filter(due_date__lt=today)
    if search:
        parcelas = parcelas.filter(
            Q(entry__patient__name__unaccent__icontains=search)
            | Q(entry__payer__unaccent__icontains=search)
            | Q(entry__description__unaccent__icontains=search)
        )
    parcelas = parcelas.order_by("due_date", "pk")
    page = Paginator(parcelas, PER_PAGE).get_page(request.GET.get("pagina"))
    for installment in page:
        installment.status = services.status(installment, today)
    return render(
        request,
        "finance/list.html",
        {
            "kind": kind,
            "pagar": kind == Entry.Kind.PAYABLE,
            "pagina": page,
            "status": status,
            "busca": search,
            "parametros": urlencode({"status": status, "q": search}),
        },
    )


@requires_permission(Module.RECEIVING, Action.CREATE)
def new_entry(request):
    inicial = {}
    code = request.GET.get("patient", "")
    patient = None
    if code.isdecimal():
        patient = Patient.objects.filter(pk=int(code), archived=False).first()
        if patient is not None:
            inicial["patient"] = patient.pk
    form = ReceivableEntryForm(request.POST or None, initial=inicial, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        entry = services.create_entry(
            clinic=request.clinic,
            kind=Entry.Kind.RECEIVABLE,
            patient=data["patient"],
            payer="" if data["patient"] else data["payer"].strip(),
            description=data["description"],
            category=data["category"],
            cost_center=data.get("cost_center"),
            practitioner=data["practitioner"],
            notes=data["notes"],
            total_amount=data["total_amount"],
            parcelas=data["parcelas"],
            primeiro_vencimento=data["primeiro_vencimento"],
            user=request.user,
        )
        if data["recebido_agora"]:
            primeira = entry.parcelas.order_by("number").first()
            payment = services.receive(
                primeira,
                user=request.user,
                amount=primeira.amount,
                method=data["method"],
                account=data["account"],
            )
            messages.success(request, _("Lançamento criado e 1ª parcela recebida."))
            return redirect("finance:receipt", pk=payment.pk)
        messages.success(request, _("Lançamento criado."))
        return redirect("finance:entry", pk=entry.pk)
    if patient is None and form["patient"].value():
        patient = Patient.objects.filter(pk=form["patient"].value()).first()
    return render(request, "finance/entry_form.html", {"form": form, "patient": patient})


@requires_permission(Module.FINANCE, Action.CREATE)
def new_expense(request):
    form = PayableEntryForm(
        request.POST or None,
        clinic=request.clinic,
        initial={"supplier": request.GET.get("supplier")},
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        entry = services.create_entry(
            clinic=request.clinic,
            kind=Entry.Kind.PAYABLE,
            supplier=data["supplier"],
            payer=data["payer"].strip(),
            description=data["description"],
            category=data["category"],
            cost_center=data.get("cost_center"),
            notes=data["notes"],
            total_amount=form.total_amount(),
            parcelas=data["parcelas"],
            primeiro_vencimento=data["primeiro_vencimento"],
            user=request.user,
        )
        if data["pago_agora"]:
            primeira = entry.parcelas.order_by("number").first()
            services.receive(
                primeira,
                user=request.user,
                amount=primeira.amount,
                method=data["method"],
                account=data["account"],
            )
        messages.success(request, _("Despesa lançada."))
        return redirect("finance:entry", pk=entry.pk)
    return render(request, "finance/expense_form.html", {"form": form})


@requires_permission(Module.RECEIVING, Action.VIEW)
def entry(request, pk):
    entry = get_object_or_404(
        Entry.objects.select_related("patient", "category", "cost_center", "practitioner"),
        pk=pk,
    )
    _require(request, entry.kind, Action.VIEW)
    today = timezone.localdate()
    parcelas = list(Installment.objects.with_balance().filter(entry=entry).select_related("entry"))
    pagamentos = Payment.objects.filter(installment__entry=entry).select_related(
        "installment", "account", "created_by"
    )
    for installment in parcelas:
        installment.status = services.status(installment, today)
        installment.lista_pagamentos = [p for p in pagamentos if p.installment_id == installment.pk]
    return render(
        request,
        "finance/entry.html",
        {
            "entry": entry,
            "pagar": entry.kind == Entry.Kind.PAYABLE,
            "pode_alterar": can(request, _module(entry.kind), Action.CREATE),
            "pode_excluir": can(request, _module(entry.kind), Action.DELETE),
            "parcelas": parcelas,
            "total_pago": sum(p.pago for p in parcelas),
            "total_saldo": sum(p.balance for p in parcelas) if not entry.cancelled else 0,
            "commission": Commission.objects.filter(entry=entry).first(),
        },
    )


@requires_permission(Module.RECEIVING, Action.DELETE)
def cancel_entry(request, pk):
    entry = get_object_or_404(Entry.objects, pk=pk, cancelled=False)
    _require(request, entry.kind, Action.DELETE)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.cancel(entry, reason=form.cleaned_data["reason"], user=request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0])
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


@requires_permission(Module.RECEIVING, Action.CREATE)
def receive(request, pk):
    installment = get_object_or_404(
        Installment.objects.with_balance().select_related("entry__patient"),
        pk=pk,
        entry__cancelled=False,
    )
    _require(request, installment.entry.kind, Action.CREATE)
    pay = installment.entry.kind == Entry.Kind.PAYABLE
    if installment.balance <= 0:
        messages.info(request, _("Esta parcela já está paga."))
        return redirect("finance:entry", pk=installment.entry_id)
    pode_desconto = can(request, Module.FINANCE, Action.CHANGE)
    conta_padrao = FinancialAccount.objects.filter(
        active=True, kind=FinancialAccount.Kind.CASH
    ).first()
    form = ReceivePaymentForm(
        request.POST or None,
        initial={
            "amount": installment.balance,
            "date": timezone.localdate(),
            "account": conta_padrao,
        },
        pode_dar_desconto=pode_desconto,
    )
    if pay:
        form.fields["amount"].label = _("Valor pago")
        form.fields["interest"].help_text = _("Já incluídos no valor pago.")
    if request.method == "POST" and form.is_valid():
        data = {field: value for field, value in form.cleaned_data.items() if field in form.fields}
        data.setdefault("discount", 0)
        data["interest"] = data.get("interest") or 0
        try:
            payment = services.receive(installment, user=request.user, **data)
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            messages.success(request, _("Pagamento registrado."))
            if pay:
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
            "pagar": pay,
        },
    )


@requires_permission(Module.RECEIVING, Action.VIEW)
def receipt(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related(
            "installment__entry__patient",
            "installment__entry__practitioner",
            "account",
            "created_by",
        ),
        pk=pk,
        installment__entry__kind=Entry.Kind.RECEIVABLE,
    )
    return render(
        request,
        "finance/receipt.html",
        {
            "payment": payment,
            "entry": payment.installment.entry,
            "total_parcelas": payment.installment.entry.parcelas.count(),
            # Where a tax document is required, the receipt says it does not replace it.
            "documento_fiscal": legislation.for_country().fiscal,
        },
    )


@requires_permission(Module.RECEIVING, Action.DELETE)
def reverse_payment(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("installment__entry"), pk=pk, reversed=False
    )
    _require(request, payment.installment.entry.kind, Action.DELETE)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.reverse_payment(payment, reason=form.cleaned_data["reason"], user=request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0])
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


@requires_permission(Module.RECEIVING, Action.VIEW)
def debtors(request):
    rows = services.debtors()
    search = request.GET.get("q", "").strip()
    encontrados = rows
    if search:
        termo = alphabetical_key(search)
        encontrados = [row for row in rows if termo in alphabetical_key(row["name"])]
    # A clinic with years of use has thousands of debtors: one page held them all (volume
    # test, decision 108). The totals still add up everyone.
    page = Paginator(encontrados, PER_PAGE).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/debtors.html",
        {
            "pagina": page,
            "busca": search,
            "parametros": urlencode({"q": search}),
            "total_vencido": sum(row["vencido"] for row in rows),
            "total_a_vencer": sum(row["a_vencer"] for row in rows),
        },
    )


# --- Daily cash drawer (0.17.0) ---------------------------------------------------------


@requires_permission(Module.RECEIVING, Action.VIEW)
def cash_register(request):
    """The drawer of a cash account: its open session, or the form to open it."""
    contas = list(FinancialAccount.objects.filter(kind=FinancialAccount.Kind.CASH, active=True))
    escolhida = request.GET.get("account", "")
    account = next((c for c in contas if str(c.pk) == escolhida), contas[0] if contas else None)
    if account is not None:
        is_open = services.open_cash_register(account)
        if is_open is not None:
            return redirect("finance:cash_detail", pk=is_open.pk)
    balance = dict(services.account_balances()).get(account) if account else None
    # Empty on purpose: the opening amount is what is counted, not the system balance.
    form = OpenCashRegisterForm(request.POST or None)
    if request.method == "POST" and account is not None:
        if not can(request, Module.RECEIVING, Action.CREATE):
            raise PermissionDenied
        if form.is_valid():
            try:
                new = services.open_register(
                    account, amount=form.cleaned_data["amount"], user=request.user
                )
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect(f"{request.path}?account={account.pk}")
            messages.success(request, _("Caixa aberto."))
            return redirect("finance:cash_detail", pk=new.pk)
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


@requires_permission(Module.RECEIVING, Action.VIEW)
def cash_register_detail(request, pk):
    session = get_object_or_404(
        CashRegister.objects.select_related("account", "opened_by", "closed_by"), pk=pk
    )
    return render(
        request,
        "finance/cash_detail.html",
        {"cash_register": session, "resumo": services.register_summary(session)},
    )


# The kind of cash movement in the URL (decision 155) and the value the database stores.
URL_MOVEMENTS = {
    "withdrawal": CashMovement.Kind.WITHDRAWAL,
    "top-up": CashMovement.Kind.TOP_UP,
}


@requires_permission(Module.RECEIVING, Action.CREATE)
def cash_movement_view(request, pk, kind):
    session = get_object_or_404(
        CashRegister.objects.select_related("account"), pk=pk, closed_at=None
    )
    if kind not in URL_MOVEMENTS:
        raise Http404
    kind = URL_MOVEMENTS[kind]
    form = CashMovementForm(request.POST or None, cash_register=session)
    if request.method == "POST" and form.is_valid():
        try:
            services.move_cash(session, kind=kind, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            messages.success(request, _("Movimento registrado."))
            return redirect("finance:cash_detail", pk=session.pk)
    return render(
        request,
        "finance/cash_form.html",
        {"cash_register": session, "form": form, "titulo": CashMovement.Kind(kind).label},
    )


@requires_permission(Module.RECEIVING, Action.CREATE)
def close_cash_register(request, pk):
    session = get_object_or_404(
        CashRegister.objects.select_related("account"), pk=pk, closed_at=None
    )
    form = CloseCashRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.close_register(session, user=request.user, **form.cleaned_data)
        messages.success(request, _("Caixa fechado."))
        return redirect("finance:cash_detail", pk=session.pk)
    return render(
        request,
        "finance/cash_form.html",
        {
            "cash_register": session,
            "form": form,
            "titulo": _("Fechar caixa"),
            "esperado": services.register_summary(session)["esperado"],
        },
    )


# --- Cash flow and reports (administrators) ---------------------------------------------


def _period(request):
    """(de, ate) from the query string; the current month by default (at most 2 years)."""
    today = timezone.localdate()
    inicio_do_mes = today.replace(day=1)
    fim_do_mes = services.add_months(inicio_do_mes, 1) - datetime.timedelta(days=1)
    try:
        since = datetime.date.fromisoformat(request.GET.get("de", ""))
    except ValueError:
        since = inicio_do_mes
    try:
        until = datetime.date.fromisoformat(request.GET.get("until", ""))
    except ValueError:
        until = fim_do_mes
    if until < since or (until - since).days > 731:
        since, until = inicio_do_mes, fim_do_mes
    return since, until


@requires_permission(Module.FINANCE, Action.VIEW)
def cash_flow(request):
    since, until = _period(request)
    por_mes = request.GET.get("agrupar") == "mes"
    return render(
        request,
        "finance/cash_flow.html",
        {
            "de": since,
            "until": until,
            "por_mes": por_mes,
            "fluxo": services.cash_flow(since, until, por_mes=por_mes),
            "contas": services.account_balances(),
        },
    )


@requires_permission(Module.FINANCE, Action.VIEW)
def reports(request):
    since, until = _period(request)
    return render(
        request,
        "finance/reports.html",
        {
            "de": since,
            "until": until,
            "relatorio": services.report(since, until),
            "fechado_ate": services.closed_until(request.clinic.pk),
        },
    )


# --- Yearly planning (decision 098) ---------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def planning(request):
    """Goals of the year per group of the chart of accounts, next to what was done."""
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
    except ValueError:
        year = today.year
    year = min(max(year, 2000), today.year + 5)
    pode_alterar = can(request, Module.FINANCE, Action.CHANGE)
    grupos = services.link_groups(AccountGroup.objects.filter(active=True))
    metas = dict(Planning.objects.filter(year=year).values_list("group_id", "amount"))
    form = PlanningForm(request.POST or None, grupos=grupos, metas=metas)
    if request.method == "POST":
        if not pode_alterar:
            raise PermissionDenied
        if request.POST.get("acao") == "copiar":
            copiadas = services.copy_targets(year)
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
            services.save_targets(year, form.paid_and_balance())
            messages.success(request, _("Planejamento salvo."))
            return redirect(f"{reverse('finance:planning')}?year={year}")
    data = services.planning(year)
    for secao in data["secoes"]:
        for row in secao["linhas"]:
            if pode_alterar and row["group"].active:
                row["campo"] = form[PlanningForm.name(row["group"])]
    return render(
        request,
        "finance/planning.html",
        {
            **data,
            "form": form,
            "pode_alterar": pode_alterar,
            "ano_anterior": year - 1,
            "proximo_ano": year + 1,
            "tem_metas_anteriores": Planning.objects.filter(year=year - 1).exists(),
        },
    )


# --- Closing the books (decision 096) -------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def book_closing(request):
    """Close the books up to a date, or reopen them with a reason. Public demo logins only
    look: one visitor closing the books would block everyone else's payments."""
    demo = request.user.demo
    pode_fechar = can(request, Module.FINANCE, Action.CHANGE) and not demo
    pode_reabrir = can(request, Module.FINANCE, Action.DELETE) and not demo
    if request.method == "POST":
        acao = request.POST.get("acao")
        if not {"fechar": pode_fechar, "reabrir": pode_reabrir}.get(acao):
            raise PermissionDenied
        form = (CloseBooksForm if acao == "fechar" else ReopenBooksForm)(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                if acao == "fechar":
                    services.close_books(request.clinic, data["until"], user=request.user)
                    messages.success(request, _("Financeiro fechado."))
                else:
                    services.reopen_books(
                        request.clinic, data["until"], reason=data["reason"], user=request.user
                    )
                    messages.success(request, _("Período reaberto."))
            except ValidationError as error:
                messages.error(request, error.messages[0])
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
        return redirect("finance:closing")
    return render(
        request,
        "finance/closing.html",
        {
            "fechado_ate": services.closed_until(request.clinic.pk),
            "historico": BookClosing.objects.select_related("created_by")[:30],
            "fechar_form": CloseBooksForm() if pode_fechar else None,
            "reabrir_form": ReopenBooksForm() if pode_reabrir else None,
        },
    )


# --- Accounts, categories and cost centers (administrators) ----------------------------


CATALOGS = {
    "categories": (Category, CategoryForm),
    "accounts": (FinancialAccount, FinancialAccountForm),
    "cost-centers": (CostCenter, CostCenterForm),
}


@requires_permission(Module.FINANCE, Action.VIEW)
def catalog_list(request, cadastro):
    modelo, _form = CATALOGS[cadastro]
    return render(
        request,
        "finance/catalog_list.html",
        {"cadastro": cadastro, "itens": modelo.objects.all(), "modelo": modelo._meta},
    )


@requires_permission(Module.FINANCE, Action.CHANGE)
def catalog_form(request, cadastro, pk=None):
    modelo, classe = CATALOGS[cadastro]
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


@requires_permission(Module.FINANCE, Action.VIEW)
def chart_of_accounts(request):
    """The chart of accounts as a tree: groups, subgroups and their categories."""
    grupos = services.link_groups(AccountGroup.objects.all())
    categorias = list(Category.objects.all())
    arvores = []
    for kind, label in Category.Kind.choices:
        rows = []

        def descer(parent_id, nivel, kind=kind, rows=rows):
            for group in (g for g in grupos if g.kind == kind and g.parent_id == parent_id):
                rows.append({"nivel": nivel, "group": group})
                rows.extend(
                    {"nivel": nivel + 1, "category": c}
                    for c in categorias
                    if c.group_id == group.pk
                )
                descer(group.pk, nivel + 1)

        descer(None, 0)
        sem_grupo = [c for c in categorias if c.kind == kind and c.group_id is None]
        arvores.append({"rotulo": label, "linhas": rows, "sem_grupo": sem_grupo})
    return render(request, "finance/chart_of_accounts.html", {"arvores": arvores})


@requires_permission(Module.FINANCE, Action.CREATE)
def new_group(request):
    return _group_form(request, AccountGroup(kind=request.GET.get("kind") or None))


@requires_permission(Module.FINANCE, Action.CHANGE)
def edit_group(request, pk):
    return _group_form(request, get_object_or_404(AccountGroup.objects, pk=pk))


def _group_form(request, instancia):
    form = AccountGroupForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": group.name})
        return redirect("finance:chart_of_accounts")
    return render(request, "finance/group_form.html", {"form": form, "instancia": instancia})


# --- Suppliers (decision 093) ---------------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def suppliers(request):
    search = request.GET.get("q", "").strip()
    results = Supplier.objects.all()
    if search:
        filtro = Q(name__unaccent__icontains=search) | Q(legal_name__unaccent__icontains=search)
        document = normalize_cnpj(search)
        if any(c.isdigit() for c in document):
            filtro |= Q(tax_id__startswith=document)
        results = results.filter(filtro)
    page = Paginator(results, PER_PAGE).get_page(request.GET.get("pagina"))
    return render(
        request,
        "finance/suppliers.html",
        {"pagina": page, "busca": search, "parametros": urlencode({"q": search})},
    )


@requires_permission(Module.FINANCE, Action.VIEW)
def supplier(request, pk):
    supplier = get_object_or_404(Supplier.objects, pk=pk)
    today = timezone.localdate()
    parcelas = list(
        Installment.objects.with_balance()
        .filter(entry__supplier=supplier)
        .select_related("entry")
        .order_by("-due_date", "-pk")[:PER_PAGE]
    )
    for installment in parcelas:
        installment.status = services.status(installment, today)
    em_aberto = sum(
        (p.balance for p in Installment.objects.unpaid().filter(entry__supplier=supplier)),
        start=ZERO,
    )
    return render(
        request,
        "finance/supplier.html",
        {"supplier": supplier, "parcelas": parcelas, "em_aberto": em_aberto},
    )


@requires_permission(Module.FINANCE, Action.CREATE)
def new_supplier(request):
    return _supplier_form(request, Supplier())


@requires_permission(Module.FINANCE, Action.CHANGE)
def edit_supplier(request, pk):
    return _supplier_form(request, get_object_or_404(Supplier.objects, pk=pk))


def _supplier_form(request, instancia):
    form = SupplierForm(request.POST or None, instance=instancia, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, _("%(nome)s salvo.") % {"nome": supplier.name})
        return redirect("finance:supplier", pk=supplier.pk)
    return render(request, "finance/supplier_form.html", {"form": form, "instancia": instancia})


# --- Practitioner commission (0.19.0) --------------------------------------------------


def _until(request):
    today = timezone.localdate()
    try:
        return min(datetime.date.fromisoformat(request.GET.get("until", "")), today)
    except ValueError:
        return today


@requires_permission(Module.FINANCE, Action.VIEW)
def commission_list(request):
    until = _until(request)
    return render(
        request,
        "finance/commissions.html",
        {
            "until": until,
            "linhas": commissions.summary(until),
            "sem_percentual": Practitioner.objects.filter(active=True, commission_percentage=0),
            "historico": Commission.objects.select_related("practitioner", "entry")[:30],
        },
    )


@requires_permission(Module.FINANCE, Action.CHANGE)
def commission_percentage(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    form = CommissionPercentageForm(request.POST or None, instance=practitioner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Percentual de %(nome)s salvo.") % {"nome": practitioner.name})
        return redirect("finance:commissions")
    return render(
        request,
        "finance/commission_percentage.html",
        {"form": form, "practitioner": practitioner},
    )


@requires_permission(Module.FINANCE, Action.CREATE)
def pay_commission(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    until = _until(request)
    default = (
        Category.objects.filter(kind=Category.Kind.EXPENSE, name="Comissões", active=True).first()
        or Category.objects.filter(kind=Category.Kind.EXPENSE, active=True).first()
    )
    form = PayCommissionForm(request.POST or None, initial={"category": default})
    if request.method == "POST" and form.is_valid():
        try:
            commission = commissions.pay(
                practitioner, until=until, user=request.user, **form.cleaned_data
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect(f"{reverse('finance:commissions')}?until={until.isoformat()}")
        messages.success(request, _("Comissão lançada em A pagar."))
        return redirect("finance:entry", pk=commission.entry_id)
    return render(
        request,
        "finance/commission_pay.html",
        {"form": form, "calculo": commissions.pending(practitioner, until), "until": until},
    )


@requires_permission(Module.FINANCE, Action.VIEW)
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
        estorno.comissao_devolvida = commissions.percentage_for(
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


@requires_permission(Module.FINANCE, Action.VIEW)
def statements(request):
    form = ImportStatementForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not can(request, Module.FINANCE, Action.CREATE):
            raise PermissionDenied
        if form.is_valid():
            file = form.cleaned_data["file"]
            try:
                statement_import = reconciliation.import_statement(
                    form.cleaned_data["account"],
                    nome_arquivo=file.name,
                    content=file.read(),
                    user=request.user,
                )
            except InvalidFile as error:
                form.add_error("file", str(error))
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
                outra = reconciliation.other_bank_account(statement_import)
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
        BankTransaction.objects.filter(status=BankTransaction.Status.PENDING)
        .values("statement_import")
        .annotate(n=Count("pk"))
        .values_list("statement_import", "n")
    )
    page = Paginator(importacoes, 30).get_page(request.GET.get("pagina"))
    for statement_import in page:
        statement_import.pendentes = pendentes.get(statement_import.pk, 0)
    return render(request, "finance/statements.html", {"form": form, "pagina": page})


@requires_permission(Module.FINANCE, Action.VIEW)
def statement(request, pk):
    statement_import = get_object_or_404(StatementImport.objects.select_related("account"), pk=pk)
    transacoes = list(
        statement_import.transacoes.select_related(
            "payment__installment__entry__patient", "cash_movement__cash_register__account"
        )
    )
    por_transacao = reconciliation.candidates(transacoes)
    for transacao in transacoes:
        transacao.candidates = por_transacao.get(transacao.pk, [])
    saldo_sistema = reconciliation.system_balance(statement_import)
    return render(
        request,
        "finance/statement.html",
        {
            "statement_import": statement_import,
            "transacoes": transacoes,
            "pendentes": sum(t.status == BankTransaction.Status.PENDING for t in transacoes),
            "unicos": sum(len(t.candidates) == 1 for t in transacoes),
            "saldo_sistema": saldo_sistema,
            "diferenca": statement_import.balance - saldo_sistema
            if saldo_sistema is not None
            else None,
        },
    )


def _back_to_statement(transacao):
    return redirect(
        f"{reverse('finance:statement', args=[transacao.statement_import_id])}#t{transacao.pk}"
    )


@require_POST
@requires_permission(Module.FINANCE, Action.CHANGE)
def statement_reconcile_unique(request, pk):
    statement_import = get_object_or_404(StatementImport.objects, pk=pk)
    feitas = reconciliation.reconcile_unique(statement_import, user=request.user)
    messages.success(request, _("%(n)s transações conciliadas.") % {"n": feitas})
    return redirect("finance:statement", pk=statement_import.pk)


@require_POST
@requires_permission(Module.FINANCE, Action.CHANGE)
def transaction_action(request, pk, acao):
    transacao = get_object_or_404(BankTransaction.objects, pk=pk)
    try:
        if acao == "reconcile":
            reconciliation.reconcile(transacao, request.POST.get("chave", ""), user=request.user)
        elif acao == "ignore":
            reason = request.POST.get("reason", "").strip()[:200]
            if not reason:
                raise ValidationError(_("Informe o motivo para ignorar a transação."))
            reconciliation.ignore(transacao, reason=reason, user=request.user)
        else:
            reconciliation.undo(transacao)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return _back_to_statement(transacao)


@requires_permission(Module.FINANCE, Action.CREATE)
def transaction_entry(request, pk):
    transacao = get_object_or_404(BankTransaction.objects.select_related("account"), pk=pk)
    form = TransactionEntryForm(
        request.POST or None,
        is_incoming=transacao.is_incoming,
        initial={"description": transacao.description},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reconciliation.create_entry(transacao, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, _("Lançamento criado e conciliado."))
        return _back_to_statement(transacao)
    return render(request, "finance/transaction_entry.html", {"form": form, "transacao": transacao})
