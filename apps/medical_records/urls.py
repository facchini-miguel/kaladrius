from django.urls import path

from . import views

app_name = "medical_records"

urlpatterns = [
    path("patients/<int:patient>/new/", views.new_visit, name="new"),
    path("<int:pk>/", views.visit, name="visit"),
    path("<int:pk>/addendum/", views.addendum, name="addendum"),
    path("<int:pk>/print/", views.print_visit, name="print"),
    path("<int:pk>/certificate/", views.new_certificate, name="certificate_new"),
    path("<int:pk>/prescription/", views.new_prescription, name="prescription_new"),
    path("certificates/<int:pk>/", views.certificate, name="certificate"),
    path("prescriptions/<int:pk>/", views.prescription, name="prescription"),
    path("<int:pk>/exams/", views.new_exam_request, name="exam_request_new"),
    path("exams/<int:pk>/", views.exam_request, name="exam_request"),
    path("<int:pk>/attachments/", views.upload_attachment, name="attachment_upload"),
    path("attachments/<int:pk>/", views.attachment, name="attachment"),
    path("attachments/<int:pk>/remove/", views.remove_attachment, name="attachment_remove"),
]
