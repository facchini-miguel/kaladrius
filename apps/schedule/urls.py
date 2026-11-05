from django.urls import path

from . import views

app_name = "schedule"

urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("events/", views.events, name="events"),
    path("new/", views.new_appointment, name="new"),
    path("<int:pk>/edit/", views.edit_appointment, name="edit"),
    path("<int:pk>/delete/", views.delete_appointment, name="delete"),
    path("<int:pk>/status/", views.status, name="status"),
    path("birthdays/", views.birthdays, name="birthdays"),
    path("birthdays/today/", views.birthdays_on_day, name="birthdays_today"),
    path("types/", views.appointment_types, name="types"),
    path("types/new/", views.new_appointment_type, name="type_new"),
    path("types/<int:pk>/edit/", views.edit_appointment_type, name="type_edit"),
    path("types/<int:pk>/delete/", views.delete_appointment_type, name="type_delete"),
]
