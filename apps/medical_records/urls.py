from django.urls import path

from . import views

app_name = "medical_records"

urlpatterns = [
    path("patients/<int:patient>/new/", views.novo, name="new"),
    path("<int:pk>/", views.atendimento, name="visit"),
    path("<int:pk>/addendum/", views.adendo, name="addendum"),
    path("<int:pk>/print/", views.imprimir, name="print"),
    path("<int:pk>/certificate/", views.atestado_novo, name="certificate_new"),
    path("<int:pk>/prescription/", views.receita_nova, name="prescription_new"),
    path("certificates/<int:pk>/", views.atestado, name="certificate"),
    path("prescriptions/<int:pk>/", views.receita, name="prescription"),
    path("<int:pk>/exams/", views.pedido_de_exames_novo, name="exam_request_new"),
    path("exams/<int:pk>/", views.pedido_de_exames, name="exam_request"),
    path("<int:pk>/attachments/", views.anexo_enviar, name="attachment_upload"),
    path("attachments/<int:pk>/", views.anexo, name="attachment"),
    path("attachments/<int:pk>/remove/", views.anexo_remover, name="attachment_remove"),
]
