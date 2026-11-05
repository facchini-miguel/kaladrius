from django.urls import path

from . import views

app_name = "practitioners"

urlpatterns = [
    path("", views.practitioner_list, name="list"),
    path("new/", views.new_practitioner, name="new"),
    path("<int:pk>/edit/", views.edit_practitioner, name="edit"),
    path("<int:pk>/delete/", views.delete_practitioner, name="delete"),
]
