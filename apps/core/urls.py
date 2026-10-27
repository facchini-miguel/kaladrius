from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("clinica/trocar/", views.trocar_clinica, name="trocar_clinica"),
    path("conta/senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
    path("clinica/configuracoes/", views.configuracoes, name="configuracoes"),
]
