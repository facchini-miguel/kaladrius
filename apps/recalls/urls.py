from django.urls import path

from . import views

app_name = "recalls"

urlpatterns = [
    path("", views.lista, name="list"),
    path("new/", views.novo, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/complete/", views.concluir, name="complete"),
    path("<int:pk>/delete/", views.excluir, name="delete"),
    path("summary/", views.resumo, name="summary"),
    path("today/", views.do_dia, name="today"),
]
