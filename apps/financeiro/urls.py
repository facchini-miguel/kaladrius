from django.urls import path, re_path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("receber/", views.receber_lista, name="receber"),
    path("receber/novo/", views.lancamento_novo, name="lancamento_novo"),
    path("lancamentos/<int:pk>/", views.lancamento, name="lancamento"),
    path("lancamentos/<int:pk>/cancelar/", views.lancamento_cancelar, name="cancelar"),
    path("parcelas/<int:pk>/receber/", views.receber, name="receber_parcela"),
    path("pagamentos/<int:pk>/recibo/", views.recibo, name="recibo"),
    path("pagamentos/<int:pk>/estornar/", views.estornar, name="estornar"),
    path("devedores/", views.devedores, name="devedores"),
    re_path(r"^(?P<cadastro>categorias|contas)/$", views.cadastro_lista, name="cadastro"),
    re_path(r"^(?P<cadastro>categorias|contas)/novo/$", views.cadastro_form, name="cadastro_novo"),
    re_path(
        r"^(?P<cadastro>categorias|contas)/(?P<pk>[0-9]+)/$",
        views.cadastro_form,
        name="cadastro_editar",
    ),
]
