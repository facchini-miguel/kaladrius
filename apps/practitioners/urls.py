from django.urls import path

from . import views

app_name = "practitioners"

urlpatterns = [
    path("", views.lista, name="list"),
    path("new/", views.novo, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/delete/", views.excluir, name="delete"),
]
