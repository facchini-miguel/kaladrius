from django.urls import path

from . import views

app_name = "ajuda"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("tecnica/", views.tecnica, name="tecnica_indice"),
    path("tecnica/<path:caminho>", views.tecnica, name="tecnica"),
    path("<slug:pagina>/", views.manual, name="manual"),
]
