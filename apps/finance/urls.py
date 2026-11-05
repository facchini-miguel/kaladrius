from django.urls import path, re_path

from . import views

app_name = "finance"

CATALOGS = "|".join(views.CATALOGS)  # categories|accounts|cost-centers

urlpatterns = [
    path("receivables/", views.receber_lista, name="receivables"),
    path("receivables/new/", views.lancamento_novo, name="entry_new"),
    path("entries/<int:pk>/", views.entry, name="entry"),
    path("entries/<int:pk>/cancel/", views.lancamento_cancelar, name="cancel"),
    path("installments/<int:pk>/receive/", views.receber, name="receive_installment"),
    path("payments/<int:pk>/receipt/", views.recibo, name="receipt"),
    path("payments/<int:pk>/reverse/", views.estornar, name="reverse_payment"),
    path("debtors/", views.devedores, name="debtors"),
    path("payables/", views.pagar_lista, name="payables"),
    path("payables/new/", views.despesa_nova, name="expense_new"),
    path("cash-flow/", views.fluxo_de_caixa, name="cash_flow"),
    path("cash/", views.cash_register, name="cash"),
    path("cash/<int:pk>/", views.caixa_detalhe, name="cash_detail"),
    path("cash/<int:pk>/close/", views.caixa_fechar, name="cash_close"),
    path("cash/<int:pk>/<str:kind>/", views.caixa_movimento, name="cash_movement"),
    path("reports/", views.relatorios, name="reports"),
    path("closing/", views.fechamento, name="closing"),
    path("planning/", views.planejamento, name="planning"),
    path("statements/", views.extratos, name="statements"),
    path("statements/<int:pk>/", views.extrato, name="statement"),
    path(
        "statements/<int:pk>/reconcile/",
        views.extrato_conciliar_unicos,
        name="statement_reconcile",
    ),
    path(
        "transactions/<int:pk>/entry/",
        views.transacao_lancamento,
        name="transaction_entry",
    ),
    re_path(
        r"^transactions/(?P<pk>[0-9]+)/(?P<acao>reconcile|ignore|undo)/$",
        views.transacao_acao,
        name="transaction",
    ),
    path("chart-of-accounts/", views.plano_contas, name="chart_of_accounts"),
    path("chart-of-accounts/groups/new/", views.grupo_novo, name="group_new"),
    path("chart-of-accounts/groups/<int:pk>/", views.grupo_editar, name="group_edit"),
    path("suppliers/", views.fornecedores, name="suppliers"),
    path("suppliers/new/", views.fornecedor_novo, name="supplier_new"),
    path("suppliers/<int:pk>/", views.supplier, name="supplier"),
    path("suppliers/<int:pk>/edit/", views.fornecedor_editar, name="supplier_edit"),
    path("commissions/", views.comissoes_lista, name="commissions"),
    path("commissions/<int:pk>/", views.commission, name="commission"),
    path(
        "commissions/practitioner/<int:pk>/",
        views.commission_percentage,
        name="commission_percentage",
    ),
    path("commissions/practitioner/<int:pk>/pay/", views.comissao_pagar, name="commission_pay"),
    re_path(rf"^(?P<cadastro>{CATALOGS})/$", views.cadastro_lista, name="catalog"),
    re_path(rf"^(?P<cadastro>{CATALOGS})/new/$", views.cadastro_form, name="catalog_new"),
    re_path(
        rf"^(?P<cadastro>{CATALOGS})/(?P<pk>[0-9]+)/$",
        views.cadastro_form,
        name="catalog_edit",
    ),
]
