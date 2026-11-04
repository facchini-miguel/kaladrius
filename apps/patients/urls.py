from django.urls import path

from . import views

app_name = "patients"

urlpatterns = [
    path("", views.lista, name="list"),
    path("new/", views.novo, name="new"),
    path("suggestions/", views.sugestoes, name="suggestions"),
    path("birthdays/", views.aniversariantes, name="birthdays"),
    path("<int:pk>/", views.ficha, name="record"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/print/", views.imprimir, name="print"),
    path("<int:pk>/archive/", views.arquivar, name="archive"),
    path("<int:pk>/restore/", views.restaurar, name="restore"),
    path("<int:pk>/delete/", views.excluir, name="delete"),
    path("<int:pk>/related/new/", views.relacionado_novo, name="related_new"),
    path("related/<int:pk>/", views.relacionado_editar, name="related_edit"),
    path("related/<int:pk>/remove/", views.relacionado_remover, name="related_remove"),
]
