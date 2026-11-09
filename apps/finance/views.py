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
    COMMISSIONS,
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
    "open": Q(balance__gt=0, entry__cancelled=False),
    "overdue": Q(balance__gt=0, entry__cancelled=False),  # + due date before today
    "paid": Q(balance__lte=0, entry__cancelled=False),
    "all": Q(),
}


def _module(kind):
    return Module.RECEIVING if kind == Entry.Kind.RECEIVABLE else Module.FINANCE


def _require(request, kind, action):
    """Payables need the Financeiro module (administrators) for the same action."""
    if not can(request, _module(kind), action):
        raise PermissionDenied


@requires_permission(Module.RECEIVING, Action.VIEW)
def receivables(request):
    return _entry_list(request, Entry.Kind.RECEIVABLE)


@requires_permission(Module.FINANCE, Action.VIEW)
def payables(request):
    return _entry_list(request, Entry.Kind.PAYABLE)


def _entry_list(request, kind):
    today = timezone.localdate()
    status = request.GET.get("status", "open")
    search = request.GET.get("q", "").strip()
    installments = (
        Installment.objects.with_balance()
        .filter(entry__kind=kind)
        .select_related("entry__patient", "entry")
        .filter(STATUSES.get(status, STATUSES["open"]))
    )
    if status == "overdue":
        installments = installments.filter(due_date__lt=today)
    if search:
        installments = installments.filter(
            Q(entry__patient__name__unaccent__icontains=search)
            | Q(entry__payer__unaccent__icontains=search)
            | Q(entry__description__unaccent__icontains=search)
        )
    installments = installments.order_by("due_date", "pk")
    page = Paginator(installments, PER_PAGE).get_page(request.GET.get("page"))
    for installment in page:
        installment.status = services.status(installment, today)
    return render(
        request,
        "finance/list.html",
        {
            "kind": kind,
            "payable": kind == Entry.Kind.PAYABLE,
            "page": page,
            "status": status,
            "search": search,
            "query": urlencode({"status": status, "q": search}),
        },
    )


@requires_permission(Module.RECEIVING, Action.CREATE)
def new_entry(request):
    initial = {}
    code = request.GET.get("patient", "")
    patient = None
    if code.isdecimal():
        patient = Patient.objects.filter(pk=int(code), archived=False).first()
        if patient is not None:
            initial["patient"] = patient.pk
    form = ReceivableEntryForm(request.POST or None, initial=initial, clinic=request.clinic)
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
            installments=data["installments"],
            first_due_date=data["first_due_date"],
            user=request.user,
        )
        if data["received_now"]:
            first = entry.installments.order_by("number").first()
            payment = services.receive(
                first,
                user=request.user,
                amount=first.amount,
                method=data["method"],
                account=data["account"],
            )
            messages.success(request, _("Entry created and 1st installment received."))
            return redirect("finance:receipt", pk=payment.pk)
        messages.success(request, _("Entry created."))
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
            installments=data["installments"],
            first_due_date=data["first_due_date"],
            user=request.user,
        )
        if data["paid_now"]:
            first = entry.installments.order_by("number").first()
            services.receive(
                first,
                user=request.user,
                amount=first.amount,
                method=data["method"],
                account=data["account"],
            )
        messages.success(request, _("Expense recorded."))
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
    installments = list(
        Installment.objects.with_balance().filter(entry=entry).select_related("entry")
    )
    payments = Payment.objects.filter(installment__entry=entry).select_related(
        "installment", "account", "created_by"
    )
    for installment in installments:
        installment.status = services.status(installment, today)
        installment.payment_list = [p for p in payments if p.installment_id == installment.pk]
    return render(
        request,
        "finance/entry.html",
        {
            "entry": entry,
            "payable": entry.kind == Entry.Kind.PAYABLE,
            "can_change": can(request, _module(entry.kind), Action.CREATE),
            "can_delete": can(request, _module(entry.kind), Action.DELETE),
            "installments": installments,
            "total_paid": sum(p.paid for p in installments),
            "total_balance": sum(p.balance for p in installments) if not entry.cancelled else 0,
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
            messages.success(request, _("Entry cancelled."))
        return redirect("finance:entry", pk=entry.pk)
    return render(
        request,
        "finance/reason.html",
        {
            "form": form,
            "title": _("Cancel entry"),
            "subject": entry,
            "back_entry": entry.pk,
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
        messages.info(request, _("This installment is already paid."))
        return redirect("finance:entry", pk=installment.entry_id)
    can_discount = can(request, Module.FINANCE, Action.CHANGE)
    default_account = FinancialAccount.objects.filter(
        active=True, kind=FinancialAccount.Kind.CASH
    ).first()
    form = ReceivePaymentForm(
        request.POST or None,
        initial={
            "amount": installment.balance,
            "date": timezone.localdate(),
            "account": default_account,
        },
        can_give_discount=can_discount,
    )
    if pay:
        form.fields["amount"].label = _("Amount paid")
        form.fields["interest"].help_text = _("Already included in the amount paid.")
    if request.method == "POST" and form.is_valid():
        data = {field: value for field, value in form.cleaned_data.items() if field in form.fields}
        data.setdefault("discount", 0)
        data["interest"] = data.get("interest") or 0
        try:
            payment = services.receive(installment, user=request.user, **data)
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            messages.success(request, _("Payment recorded."))
            if pay:
                return redirect("finance:entry", pk=installment.entry_id)
            return redirect("finance:receipt", pk=payment.pk)
    return render(
        request,
        "finance/receive.html",
        {
            "form": form,
            "installment": installment,
            "total_installments": installment.entry.installments.count(),
            "can_discount": can_discount,
            "payable": pay,
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
            "total_installments": payment.installment.entry.installments.count(),
            # Where a tax document is required, the receipt says it does not replace it.
            "tax_document": legislation.for_country().tax_document,
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
            messages.success(request, _("Payment reversed."))
        return redirect("finance:entry", pk=payment.installment.entry_id)
    return render(
        request,
        "finance/reason.html",
        {
            "form": form,
            "title": _("Reverse payment"),
            # Not str(pagamento): that has the raw amount ("1350.00"), for the audit log.
            "subject": " · ".join(
                [
                    str(payment.installment),
                    currency(payment.amount),
                    date_format(payment.date, "SHORT_DATE_FORMAT"),
                ]
            ),
            "back_entry": payment.installment.entry_id,
        },
    )


@requires_permission(Module.RECEIVING, Action.VIEW)
def debtors(request):
    rows = services.debtors()
    search = request.GET.get("q", "").strip()
    found = rows
    if search:
        term = alphabetical_key(search)
        found = [row for row in rows if term in alphabetical_key(row["name"])]
    # A clinic with years of use has thousands of debtors: one page held them all (volume
    # test, decision 108). The totals still add up everyone.
    page = Paginator(found, PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "finance/debtors.html",
        {
            "page": page,
            "search": search,
            "query": urlencode({"q": search}),
            "total_overdue": sum(row["overdue"] for row in rows),
            "total_upcoming": sum(row["not_yet_due"] for row in rows),
        },
    )


# --- Daily cash drawer (0.17.0) ---------------------------------------------------------


@requires_permission(Module.RECEIVING, Action.VIEW)
def cash_register(request):
    """The drawer of a cash account: its open session, or the form to open it."""
    accounts = list(FinancialAccount.objects.filter(kind=FinancialAccount.Kind.CASH, active=True))
    chosen = request.GET.get("account", "")
    account = next((c for c in accounts if str(c.pk) == chosen), accounts[0] if accounts else None)
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
            messages.success(request, _("Drawer opened."))
            return redirect("finance:cash_detail", pk=new.pk)
    history = CashRegister.objects.filter(account=account).select_related("opened_by", "closed_by")[
        :30
    ]
    return render(
        request,
        "finance/cash.html",
        {
            "accounts": accounts,
            "account": account,
            "form": form,
            "system_balance": balance,
            "history": history,
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
        {"cash_register": session, "summary": services.register_summary(session)},
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
            messages.success(request, _("Movement recorded."))
            return redirect("finance:cash_detail", pk=session.pk)
    return render(
        request,
        "finance/cash_form.html",
        {"cash_register": session, "form": form, "title": CashMovement.Kind(kind).label},
    )


@requires_permission(Module.RECEIVING, Action.CREATE)
def close_cash_register(request, pk):
    session = get_object_or_404(
        CashRegister.objects.select_related("account"), pk=pk, closed_at=None
    )
    form = CloseCashRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.close_register(session, user=request.user, **form.cleaned_data)
        messages.success(request, _("Drawer closed."))
        return redirect("finance:cash_detail", pk=session.pk)
    return render(
        request,
        "finance/cash_form.html",
        {
            "cash_register": session,
            "form": form,
            "title": _("Close drawer"),
            "expected": services.register_summary(session)["expected"],
        },
    )


# --- Cash flow and reports (administrators) ---------------------------------------------


def _period(request):
    """(since, until) from the query string; the current month by default (at most 2 years)."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    end_of_month = services.add_months(month_start, 1) - datetime.timedelta(days=1)
    try:
        since = datetime.date.fromisoformat(request.GET.get("since", ""))
    except ValueError:
        since = month_start
    try:
        until = datetime.date.fromisoformat(request.GET.get("until", ""))
    except ValueError:
        until = end_of_month
    if until < since or (until - since).days > 731:
        since, until = month_start, end_of_month
    return since, until


@requires_permission(Module.FINANCE, Action.VIEW)
def cash_flow(request):
    since, until = _period(request)
    by_month = request.GET.get("group") == "month"
    return render(
        request,
        "finance/cash_flow.html",
        {
            "since": since,
            "until": until,
            "by_month": by_month,
            "flow": services.cash_flow(since, until, by_month=by_month),
            "accounts": services.account_balances(),
        },
    )


@requires_permission(Module.FINANCE, Action.VIEW)
def reports(request):
    since, until = _period(request)
    return render(
        request,
        "finance/reports.html",
        {
            "since": since,
            "until": until,
            "report": services.report(since, until),
            "closed_until": services.closed_until(request.clinic.pk),
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
    can_change = can(request, Module.FINANCE, Action.CHANGE)
    groups = services.link_groups(AccountGroup.objects.filter(active=True))
    goals = dict(Planning.objects.filter(year=year).values_list("group_id", "amount"))
    form = PlanningForm(request.POST or None, groups=groups, goals=goals)
    if request.method == "POST":
        if not can_change:
            raise PermissionDenied
        if request.POST.get("action") == "copy":
            copied = services.copy_targets(year)
            messages.success(
                request,
                ngettext(
                    "%(n)s goal copied from last year.",
                    "%(n)s goals copied from last year.",
                    copied,
                )
                % {"n": copied},
            )
            return redirect(f"{reverse('finance:planning')}?year={year}")
        if form.is_valid():
            services.save_targets(year, form.paid_and_balance())
            messages.success(request, _("Plan saved."))
            return redirect(f"{reverse('finance:planning')}?year={year}")
    data = services.planning(year)
    for section in data["sections"]:
        for row in section["rows"]:
            if can_change and row["group"].active:
                row["field"] = form[PlanningForm.name(row["group"])]
    return render(
        request,
        "finance/planning.html",
        {
            **data,
            "form": form,
            "can_change": can_change,
            "previous_year": year - 1,
            "next_year": year + 1,
            "has_previous_targets": Planning.objects.filter(year=year - 1).exists(),
        },
    )


# --- Closing the books (decision 096) -------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def book_closing(request):
    """Close the books up to a date, or reopen them with a reason. Public demo logins only
    look: one visitor closing the books would block everyone else's payments."""
    demo = request.user.demo
    can_close = can(request, Module.FINANCE, Action.CHANGE) and not demo
    can_reopen = can(request, Module.FINANCE, Action.DELETE) and not demo
    if request.method == "POST":
        action = request.POST.get("action")
        if not {"close": can_close, "reopen": can_reopen}.get(action):
            raise PermissionDenied
        form = (CloseBooksForm if action == "close" else ReopenBooksForm)(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                if action == "close":
                    services.close_books(request.clinic, data["until"], user=request.user)
                    messages.success(request, _("Finance closed."))
                else:
                    services.reopen_books(
                        request.clinic, data["until"], reason=data["reason"], user=request.user
                    )
                    messages.success(request, _("Period reopened."))
            except ValidationError as error:
                messages.error(request, error.messages[0])
        else:
            messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
        return redirect("finance:closing")
    return render(
        request,
        "finance/closing.html",
        {
            "closed_until": services.closed_until(request.clinic.pk),
            "history": BookClosing.objects.select_related("created_by")[:30],
            "close_form": CloseBooksForm() if can_close else None,
            "reopen_form": ReopenBooksForm() if can_reopen else None,
        },
    )


# --- Accounts, categories and cost centers (administrators) ----------------------------


CATALOGS = {
    "categories": (Category, CategoryForm),
    "accounts": (FinancialAccount, FinancialAccountForm),
    "cost-centers": (CostCenter, CostCenterForm),
}


@requires_permission(Module.FINANCE, Action.VIEW)
def catalog_list(request, catalog):
    model, _form = CATALOGS[catalog]
    return render(
        request,
        "finance/catalog_list.html",
        {"catalog": catalog, "items": model.objects.all(), "model": model._meta},
    )


@requires_permission(Module.FINANCE, Action.CHANGE)
def catalog_form(request, catalog, pk=None):
    model, form_class = CATALOGS[catalog]
    instance = get_object_or_404(model.objects, pk=pk) if pk else model()
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("%(name)s saved.") % {"name": form.instance.name})
        return redirect("finance:catalog", catalog=catalog)
    return render(
        request,
        "finance/catalog_form.html",
        {"form": form, "catalog": catalog, "instance": instance, "model": model._meta},
    )


# --- Chart of accounts (decision 097) ---------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def chart_of_accounts(request):
    """The chart of accounts as a tree: groups, subgroups and their categories."""
    groups = services.link_groups(AccountGroup.objects.all())
    categories = list(Category.objects.all())
    trees = []
    for kind, label in Category.Kind.choices:
        rows = []

        def walk_down(parent_id, level, kind=kind, rows=rows):
            for group in (g for g in groups if g.kind == kind and g.parent_id == parent_id):
                rows.append({"level": level, "group": group})
                rows.extend(
                    {"level": level + 1, "category": c}
                    for c in categories
                    if c.group_id == group.pk
                )
                walk_down(group.pk, level + 1)

        walk_down(None, 0)
        ungrouped = [c for c in categories if c.kind == kind and c.group_id is None]
        trees.append({"label": label, "rows": rows, "ungrouped": ungrouped})
    return render(request, "finance/chart_of_accounts.html", {"trees": trees})


@requires_permission(Module.FINANCE, Action.CREATE)
def new_group(request):
    return _group_form(request, AccountGroup(kind=request.GET.get("kind") or None))


@requires_permission(Module.FINANCE, Action.CHANGE)
def edit_group(request, pk):
    return _group_form(request, get_object_or_404(AccountGroup.objects, pk=pk))


def _group_form(request, instance):
    form = AccountGroupForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, _("%(name)s saved.") % {"name": group.name})
        return redirect("finance:chart_of_accounts")
    return render(request, "finance/group_form.html", {"form": form, "instance": instance})


# --- Suppliers (decision 093) ---------------------------------------------------------


@requires_permission(Module.FINANCE, Action.VIEW)
def suppliers(request):
    search = request.GET.get("q", "").strip()
    results = Supplier.objects.all()
    if search:
        query_filter = Q(name__unaccent__icontains=search) | Q(
            legal_name__unaccent__icontains=search
        )
        document = normalize_cnpj(search)
        if any(c.isdigit() for c in document):
            query_filter |= Q(tax_id__startswith=document)
        results = results.filter(query_filter)
    page = Paginator(results, PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "finance/suppliers.html",
        {"page": page, "search": search, "query": urlencode({"q": search})},
    )


@requires_permission(Module.FINANCE, Action.VIEW)
def supplier(request, pk):
    supplier = get_object_or_404(Supplier.objects, pk=pk)
    today = timezone.localdate()
    installments = list(
        Installment.objects.with_balance()
        .filter(entry__supplier=supplier)
        .select_related("entry")
        .order_by("-due_date", "-pk")[:PER_PAGE]
    )
    for installment in installments:
        installment.status = services.status(installment, today)
    outstanding = sum(
        (p.balance for p in Installment.objects.unpaid().filter(entry__supplier=supplier)),
        start=ZERO,
    )
    return render(
        request,
        "finance/supplier.html",
        {"supplier": supplier, "installments": installments, "outstanding": outstanding},
    )


@requires_permission(Module.FINANCE, Action.CREATE)
def new_supplier(request):
    return _supplier_form(request, Supplier())


@requires_permission(Module.FINANCE, Action.CHANGE)
def edit_supplier(request, pk):
    return _supplier_form(request, get_object_or_404(Supplier.objects, pk=pk))


def _supplier_form(request, instance):
    form = SupplierForm(request.POST or None, instance=instance, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, _("%(name)s saved.") % {"name": supplier.name})
        return redirect("finance:supplier", pk=supplier.pk)
    return render(request, "finance/supplier_form.html", {"form": form, "instance": instance})


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
            "rows": commissions.summary(until),
            "without_percentage": Practitioner.objects.filter(active=True, commission_percentage=0),
            "history": Commission.objects.select_related("practitioner", "entry")[:30],
        },
    )


@requires_permission(Module.FINANCE, Action.CHANGE)
def commission_percentage(request, pk):
    practitioner = get_object_or_404(Practitioner.objects, pk=pk)
    form = CommissionPercentageForm(request.POST or None, instance=practitioner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Percentage of %(name)s saved.") % {"name": practitioner.name})
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
        Category.objects.filter(key=COMMISSIONS, active=True).first()
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
        messages.success(request, _("Commission added to Payables."))
        return redirect("finance:entry", pk=commission.entry_id)
    return render(
        request,
        "finance/commission_pay.html",
        {"form": form, "calculation": commissions.pending(practitioner, until), "until": until},
    )


@requires_permission(Module.FINANCE, Action.VIEW)
def commission(request, pk):
    commission = get_object_or_404(
        Commission.objects.select_related("practitioner", "entry"), pk=pk
    )
    payments = commission.payments.select_related("installment__entry__patient").order_by(
        "date", "pk"
    )
    reversal_deduction = commission.reversed_payments.select_related(
        "installment__entry__patient", "commission"
    ).order_by("date", "pk")
    for reversal in reversal_deduction:
        reversal.commission_returned = commissions.percentage_for(
            reversal.amount, reversal.commission.percentage
        )
    return render(
        request,
        "finance/commission.html",
        {
            "commission": commission,
            "payments": payments,
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
                    file_name=file.name,
                    content=file.read(),
                    user=request.user,
                )
            except InvalidFile as error:
                form.add_error("file", str(error))
            else:
                messages.success(
                    request,
                    _(
                        "Statement imported: %(new_ones)s new transactions, %(repeated)s already "
                        "imported."
                    )
                    % {
                        "new_ones": statement_import.new_transactions,
                        "repeated": statement_import.duplicate_transactions,
                    },
                )
                if statement_import.unreadable_transactions:
                    messages.warning(
                        request,
                        ngettext(
                            "%(n)s line of the file had no readable date or amount and was not "
                            "imported. Check it on the bank statement.",
                            "%(n)s lines of the file had no readable date or amount and were not "
                            "imported. Check them on the bank statement.",
                            statement_import.unreadable_transactions,
                        )
                        % {"n": statement_import.unreadable_transactions},
                    )
                other = reconciliation.other_bank_account(statement_import)
                if other:
                    messages.warning(
                        request,
                        _(
                            "Warning: this file is from bank account %(new)s, but the previous "
                            "one imported into %(account)s was from account %(old)s."
                        )
                        % {
                            "new": statement_import.bank_account_number,
                            "account": statement_import.account,
                            "old": other,
                        },
                    )
                return redirect("finance:statement", pk=statement_import.pk)
    imports = StatementImport.objects.select_related("account", "created_by")
    pending = dict(
        BankTransaction.objects.filter(status=BankTransaction.Status.PENDING)
        .values("statement_import")
        .annotate(n=Count("pk"))
        .values_list("statement_import", "n")
    )
    page = Paginator(imports, 30).get_page(request.GET.get("page"))
    for statement_import in page:
        statement_import.pending = pending.get(statement_import.pk, 0)
    return render(request, "finance/statements.html", {"form": form, "page": page})


@requires_permission(Module.FINANCE, Action.VIEW)
def statement(request, pk):
    statement_import = get_object_or_404(StatementImport.objects.select_related("account"), pk=pk)
    transactions = list(
        statement_import.transactions.select_related(
            "payment__installment__entry__patient", "cash_movement__cash_register__account"
        )
    )
    by_transaction = reconciliation.candidates(transactions)
    for bank_transaction in transactions:
        bank_transaction.candidates = by_transaction.get(bank_transaction.pk, [])
    system_balance = reconciliation.system_balance(statement_import)
    return render(
        request,
        "finance/statement.html",
        {
            "statement_import": statement_import,
            "transactions": transactions,
            "pending": sum(t.status == BankTransaction.Status.PENDING for t in transactions),
            "unique": sum(len(t.candidates) == 1 for t in transactions),
            "system_balance": system_balance,
            "difference": statement_import.balance - system_balance
            if system_balance is not None
            else None,
        },
    )


def _back_to_statement(bank_transaction):
    url = reverse("finance:statement", args=[bank_transaction.statement_import_id])
    return redirect(f"{url}#t{bank_transaction.pk}")


@require_POST
@requires_permission(Module.FINANCE, Action.CHANGE)
def statement_reconcile_unique(request, pk):
    statement_import = get_object_or_404(StatementImport.objects, pk=pk)
    done = reconciliation.reconcile_unique(statement_import, user=request.user)
    messages.success(request, _("%(n)s transactions reconciled.") % {"n": done})
    return redirect("finance:statement", pk=statement_import.pk)


@require_POST
@requires_permission(Module.FINANCE, Action.CHANGE)
def transaction_action(request, pk, action):
    bank_transaction = get_object_or_404(BankTransaction.objects, pk=pk)
    try:
        if action == "reconcile":
            reconciliation.reconcile(
                bank_transaction, request.POST.get("key", ""), user=request.user
            )
        elif action == "ignore":
            reason = request.POST.get("reason", "").strip()[:200]
            if not reason:
                raise ValidationError(_("Enter the reason to ignore the transaction."))
            reconciliation.ignore(bank_transaction, reason=reason, user=request.user)
        else:
            reconciliation.undo(bank_transaction)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return _back_to_statement(bank_transaction)


@requires_permission(Module.FINANCE, Action.CREATE)
def transaction_entry(request, pk):
    bank_transaction = get_object_or_404(BankTransaction.objects.select_related("account"), pk=pk)
    form = TransactionEntryForm(
        request.POST or None,
        is_incoming=bank_transaction.is_incoming,
        initial={"description": bank_transaction.description},
    )
    if request.method == "POST" and form.is_valid():
        try:
            reconciliation.create_entry(bank_transaction, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, _("Entry created and reconciled."))
        return _back_to_statement(bank_transaction)
    return render(
        request, "finance/transaction_entry.html", {"form": form, "transaction": bank_transaction}
    )
