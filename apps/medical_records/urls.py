from django.urls import path

from . import views

app_name = "prontuario"

urlpatterns = [
    path("pacientes/<int:paciente>/novo/", views.novo, name="novo"),
    path("<int:pk>/", views.atendimento, name="atendimento"),
    path("<int:pk>/adendo/", views.adendo, name="adendo"),
    path("<int:pk>/imprimir/", views.imprimir, name="imprimir"),
    path("<int:pk>/atestado/", views.atestado_novo, name="atestado_novo"),
    path("<int:pk>/receita/", views.receita_nova, name="receita_nova"),
    path("atestados/<int:pk>/", views.atestado, name="atestado"),
    path("receitas/<int:pk>/", views.receita, name="receita"),
    path("<int:pk>/exames/", views.pedido_de_exames_novo, name="pedido_de_exames_novo"),
    path("exames/<int:pk>/", views.pedido_de_exames, name="pedido_de_exames"),
    path("<int:pk>/anexos/", views.anexo_enviar, name="anexo_enviar"),
    path("anexos/<int:pk>/", views.anexo, name="anexo"),
    path("anexos/<int:pk>/remover/", views.anexo_remover, name="anexo_remover"),
]
