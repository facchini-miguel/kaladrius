from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.calendario, name="calendario"),
    path("eventos/", views.eventos, name="eventos"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("aniversariantes/", views.aniversariantes, name="aniversariantes"),
    path("aniversariantes/dia/", views.aniversariantes_dia, name="aniversariantes_dia"),
    path("tipos/", views.tipos, name="tipos"),
    path("tipos/novo/", views.tipo_novo, name="tipo_novo"),
    path("tipos/<int:pk>/editar/", views.tipo_editar, name="tipo_editar"),
    path("tipos/<int:pk>/excluir/", views.tipo_excluir, name="tipo_excluir"),
]
