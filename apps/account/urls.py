from django.urls import path

from . import views

app_name = "conta"

urlpatterns = [
    path("login/codigo/", views.codigo, name="codigo"),
    path("ativo/", views.ativo, name="ativo"),
    path("duas-etapas/", views.duas_etapas, name="duas_etapas"),
    path("senha/esqueci/", views.recuperar, name="recuperar"),
    path("senha/esqueci/enviado/", views.recuperar_enviado, name="recuperar_enviado"),
    path("senha/nova/<uidb64>/<token>/", views.nova_senha, name="nova_senha"),
    path("senha/redefinida/", views.senha_redefinida, name="senha_redefinida"),
]
