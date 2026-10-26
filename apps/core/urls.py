from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("clinica/trocar/", views.trocar_clinica, name="trocar_clinica"),
]
