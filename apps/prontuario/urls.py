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
]
