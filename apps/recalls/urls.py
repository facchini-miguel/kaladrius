from django.urls import path

from . import views

app_name = "recalls"

urlpatterns = [
    path("", views.results, name="list"),
    path("new/", views.new, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/complete/", views.concluir, name="complete"),
    path("<int:pk>/delete/", views.excluir, name="delete"),
    path("summary/", views.summary, name="summary"),
    path("today/", views.do_dia, name="today"),
]
