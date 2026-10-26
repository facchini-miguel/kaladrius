from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("tipos/", views.tipos, name="tipos"),
    path("tipos/novo/", views.tipo_novo, name="tipo_novo"),
    path("tipos/<int:pk>/editar/", views.tipo_editar, name="tipo_editar"),
    path("tipos/<int:pk>/excluir/", views.tipo_excluir, name="tipo_excluir"),
]
