from django.urls import path

from . import views

app_name = "orcamentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/itens/", views.item_adicionar, name="item_adicionar"),
    path("<int:pk>/itens/<int:item>/remover/", views.item_remover, name="item_remover"),
    path("<int:pk>/desconto/", views.desconto, name="desconto"),
    path("<int:pk>/aprovar/", views.aprovar, name="aprovar"),
    path("<int:pk>/recusar/", views.recusar, name="recusar"),
    path("<int:pk>/imprimir/", views.imprimir, name="imprimir"),
    path("procedimentos/", views.procedimentos, name="procedimentos"),
    path("procedimentos/novo/", views.procedimento_form, name="procedimento_novo"),
    path("procedimentos/<int:pk>/", views.procedimento_form, name="procedimento_editar"),
]
