from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("", views.patient_list, name="list"),
    path("new/", views.new_patient, name="new"),
    path("suggestions/", views.suggestions, name="suggestions"),
    path("birthdays/", views.birthdays, name="birthdays"),
    path("<int:pk>/", views.patient_record, name="record"),
    path("<int:pk>/edit/", views.edit_patient, name="edit"),
    path("<int:pk>/print/", views.print_patient, name="print"),
    path("<int:pk>/archive/", views.archive, name="archive"),
    path("<int:pk>/restore/", views.restore, name="restore"),
    path("<int:pk>/delete/", views.delete_patient, name="delete"),
    path("<int:pk>/related/new/", views.new_related_person, name="related_new"),
    path("related/<int:pk>/", views.edit_related_person, name="related_edit"),
    path("related/<int:pk>/remove/", views.remove_related_person, name="related_remove"),
]
