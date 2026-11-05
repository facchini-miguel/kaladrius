from django.urls import path

from . import views

app_name = "health_plans"

urlpatterns = [
    path("", views.results, name="list"),
    path("new/", views.new, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("cards/new/<int:patient>/", views.carteirinha_nova, name="card_new"),
    path("cards/<int:pk>/edit/", views.carteirinha_editar, name="card_edit"),
]
