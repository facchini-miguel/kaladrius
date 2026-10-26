from django.urls import path

from . import views

app_name = "pacientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
