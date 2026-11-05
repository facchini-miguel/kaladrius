from django.urls import path

from . import views

app_name = "recalls"

urlpatterns = [
    path("", views.recall_list, name="list"),
    path("new/", views.new_recall, name="new"),
    path("<int:pk>/edit/", views.edit_recall, name="edit"),
    path("<int:pk>/complete/", views.complete, name="complete"),
    path("<int:pk>/delete/", views.delete_recall, name="delete"),
    path("summary/", views.summary, name="summary"),
    path("today/", views.of_day, name="today"),
]
