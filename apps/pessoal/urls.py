from django.urls import path

from . import views

app_name = "pessoal"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.funcionario, name="funcionario"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("folha/", views.folha, name="folha"),
]
