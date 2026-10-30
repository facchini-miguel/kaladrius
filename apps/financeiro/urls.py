from django.urls import path, re_path

from . import views

app_name = "financeiro"

CADASTROS = "|".join(views.CADASTROS)  # categorias|contas|centros-de-custo

urlpatterns = [
    path("receber/", views.receber_lista, name="receber"),
    path("receber/novo/", views.lancamento_novo, name="lancamento_novo"),
    path("lancamentos/<int:pk>/", views.lancamento, name="lancamento"),
    path("lancamentos/<int:pk>/cancelar/", views.lancamento_cancelar, name="cancelar"),
    path("parcelas/<int:pk>/receber/", views.receber, name="receber_parcela"),
    path("pagamentos/<int:pk>/recibo/", views.recibo, name="recibo"),
    path("pagamentos/<int:pk>/estornar/", views.estornar, name="estornar"),
    path("devedores/", views.devedores, name="devedores"),
    path("pagar/", views.pagar_lista, name="pagar"),
    path("pagar/nova/", views.despesa_nova, name="despesa_nova"),
    path("fluxo-de-caixa/", views.fluxo_de_caixa, name="fluxo"),
    path("caixa/", views.caixa, name="caixa"),
    path("caixa/<int:pk>/", views.caixa_detalhe, name="caixa_detalhe"),
    path("caixa/<int:pk>/fechar/", views.caixa_fechar, name="caixa_fechar"),
    path("caixa/<int:pk>/<str:tipo>/", views.caixa_movimento, name="caixa_movimento"),
    path("relatorios/", views.relatorios, name="relatorios"),
    path("fechamento/", views.fechamento, name="fechamento"),
    path("extratos/", views.extratos, name="extratos"),
    path("extratos/<int:pk>/", views.extrato, name="extrato"),
    path(
        "extratos/<int:pk>/conciliar/",
        views.extrato_conciliar_unicos,
        name="extrato_conciliar",
    ),
    path(
        "transacoes/<int:pk>/lancamento/",
        views.transacao_lancamento,
        name="transacao_lancamento",
    ),
    re_path(
        r"^transacoes/(?P<pk>[0-9]+)/(?P<acao>conciliar|ignorar|desfazer)/$",
        views.transacao_acao,
        name="transacao",
    ),
    path("fornecedores/", views.fornecedores, name="fornecedores"),
    path("fornecedores/novo/", views.fornecedor_novo, name="fornecedor_novo"),
    path("fornecedores/<int:pk>/", views.fornecedor, name="fornecedor"),
    path("fornecedores/<int:pk>/editar/", views.fornecedor_editar, name="fornecedor_editar"),
    path("comissoes/", views.comissoes_lista, name="comissoes"),
    path("comissoes/<int:pk>/", views.comissao, name="comissao"),
    path("comissoes/profissional/<int:pk>/", views.comissao_percentual, name="comissao_percentual"),
    path("comissoes/profissional/<int:pk>/pagar/", views.comissao_pagar, name="comissao_pagar"),
    re_path(rf"^(?P<cadastro>{CADASTROS})/$", views.cadastro_lista, name="cadastro"),
    re_path(rf"^(?P<cadastro>{CADASTROS})/novo/$", views.cadastro_form, name="cadastro_novo"),
    re_path(
        rf"^(?P<cadastro>{CADASTROS})/(?P<pk>[0-9]+)/$",
        views.cadastro_form,
        name="cadastro_editar",
    ),
]
