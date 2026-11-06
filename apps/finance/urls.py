from django.urls import path, re_path

from . import views

app_name = "finance"

CATALOGS = "|".join(views.CATALOGS)  # categories|accounts|cost-centers

urlpatterns = [
    path("receivables/", views.receivables, name="receivables"),
    path("receivables/new/", views.new_entry, name="entry_new"),
    path("entries/<int:pk>/", views.entry, name="entry"),
    path("entries/<int:pk>/cancel/", views.cancel_entry, name="cancel"),
    path("installments/<int:pk>/receive/", views.receive, name="receive_installment"),
    path("payments/<int:pk>/receipt/", views.receipt, name="receipt"),
    path("payments/<int:pk>/reverse/", views.reverse_payment, name="reverse_payment"),
    path("debtors/", views.debtors, name="debtors"),
    path("payables/", views.payables, name="payables"),
    path("payables/new/", views.new_expense, name="expense_new"),
    path("cash-flow/", views.cash_flow, name="cash_flow"),
    path("cash/", views.cash_register, name="cash"),
    path("cash/<int:pk>/", views.cash_register_detail, name="cash_detail"),
    path("cash/<int:pk>/close/", views.close_cash_register, name="cash_close"),
    path("cash/<int:pk>/<str:kind>/", views.cash_movement_view, name="cash_movement"),
    path("reports/", views.reports, name="reports"),
    path("closing/", views.book_closing, name="closing"),
    path("planning/", views.planning, name="planning"),
    path("statements/", views.statements, name="statements"),
    path("statements/<int:pk>/", views.statement, name="statement"),
    path(
        "statements/<int:pk>/reconcile/",
        views.statement_reconcile_unique,
        name="statement_reconcile",
    ),
    path(
        "transactions/<int:pk>/entry/",
        views.transaction_entry,
        name="transaction_entry",
    ),
    re_path(
        r"^transactions/(?P<pk>[0-9]+)/(?P<action>reconcile|ignore|undo)/$",
        views.transaction_action,
        name="transaction",
    ),
    path("chart-of-accounts/", views.chart_of_accounts, name="chart_of_accounts"),
    path("chart-of-accounts/groups/new/", views.new_group, name="group_new"),
    path("chart-of-accounts/groups/<int:pk>/", views.edit_group, name="group_edit"),
    path("suppliers/", views.suppliers, name="suppliers"),
    path("suppliers/new/", views.new_supplier, name="supplier_new"),
    path("suppliers/<int:pk>/", views.supplier, name="supplier"),
    path("suppliers/<int:pk>/edit/", views.edit_supplier, name="supplier_edit"),
    path("commissions/", views.commission_list, name="commissions"),
    path("commissions/<int:pk>/", views.commission, name="commission"),
    path(
        "commissions/practitioner/<int:pk>/",
        views.commission_percentage,
        name="commission_percentage",
    ),
    path("commissions/practitioner/<int:pk>/pay/", views.pay_commission, name="commission_pay"),
    re_path(rf"^(?P<catalog>{CATALOGS})/$", views.catalog_list, name="catalog"),
    re_path(rf"^(?P<catalog>{CATALOGS})/new/$", views.catalog_form, name="catalog_new"),
    re_path(
        rf"^(?P<catalog>{CATALOGS})/(?P<pk>[0-9]+)/$",
        views.catalog_form,
        name="catalog_edit",
    ),
]
