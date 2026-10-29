from django.urls import path

from . import views

app_name = "prontuario"

urlpatterns = [
    path("pacientes/<int:paciente>/novo/", views.novo, name="novo"),
    path("<int:pk>/", views.atendimento, name="atendimento"),
    path("<int:pk>/adendo/", views.adendo, name="adendo"),
]
