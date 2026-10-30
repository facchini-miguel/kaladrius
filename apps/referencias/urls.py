from django.urls import path

from . import views

app_name = "referencias"

urlpatterns = [
    path("cidades/", views.cidades, name="cidades"),
    path("cidades/opcoes/", views.opcoes_cidades, name="opcoes_cidades"),
    path("enderecos/sugestoes/", views.sugestoes_endereco, name="sugestoes_endereco"),
    path("bancos/", views.bancos, name="bancos"),
]
