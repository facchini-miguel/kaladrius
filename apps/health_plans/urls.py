from django.urls import path

from . import views

app_name = "health_plans"

urlpatterns = [
    path("", views.lista, name="list"),
    path("new/", views.novo, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("cards/new/<int:paciente>/", views.carteirinha_nova, name="card_new"),
    path("cards/<int:pk>/edit/", views.carteirinha_editar, name="card_edit"),
]
