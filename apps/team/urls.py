from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/senha/", views.senha, name="senha"),
    path("<int:pk>/duas-etapas/", views.duas_etapas, name="duas_etapas"),
]
