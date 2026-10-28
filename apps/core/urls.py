from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("clinica/cadastrar/", views.cadastrar_clinica, name="cadastrar_clinica"),
    path("conta/senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
    path("clinica/configuracoes/", views.configuracoes, name="configuracoes"),
    path("conta/idioma/", views.trocar_idioma, name="trocar_idioma"),
]
