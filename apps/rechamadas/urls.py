from django.urls import path

from . import views

app_name = "rechamadas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/concluir/", views.concluir, name="concluir"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("resumo/", views.resumo, name="resumo"),
    path("dia/", views.do_dia, name="do_dia"),
]
