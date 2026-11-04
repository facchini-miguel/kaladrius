from django.urls import path

from . import views

app_name = "estimates"

urlpatterns = [
    path("", views.lista, name="list"),
    path("new/", views.novo, name="new"),
    path("<int:pk>/", views.detalhe, name="detail"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/items/", views.item_adicionar, name="item_add"),
    path("<int:pk>/items/<int:item>/remove/", views.item_remover, name="item_remove"),
    path("<int:pk>/discount/", views.desconto, name="discount"),
    path("<int:pk>/approve/", views.aprovar, name="approve"),
    path("<int:pk>/decline/", views.recusar, name="decline"),
    path("<int:pk>/print/", views.imprimir, name="print"),
    path("procedures/", views.procedimentos, name="procedures"),
    path("procedures/new/", views.procedimento_form, name="procedure_new"),
    path("procedures/<int:pk>/", views.procedimento_form, name="procedure_edit"),
]
