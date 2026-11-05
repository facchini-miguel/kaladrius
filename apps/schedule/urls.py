from django.urls import path

from . import views

app_name = "schedule"

urlpatterns = [
    path("", views.calendario, name="calendar"),
    path("events/", views.eventos, name="events"),
    path("new/", views.new, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/delete/", views.excluir, name="delete"),
    path("<int:pk>/status/", views.status, name="status"),
    path("birthdays/", views.aniversariantes, name="birthdays"),
    path("birthdays/today/", views.aniversariantes_dia, name="birthdays_today"),
    path("types/", views.tipos, name="types"),
    path("types/new/", views.tipo_novo, name="type_new"),
    path("types/<int:pk>/edit/", views.tipo_editar, name="type_edit"),
    path("types/<int:pk>/delete/", views.tipo_excluir, name="type_delete"),
]
