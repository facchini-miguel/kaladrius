from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("", views.results, name="list"),
    path("new/", views.new, name="new"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("<int:pk>/password/", views.password, name="password"),
    path("<int:pk>/two-factor/", views.duas_etapas, name="two_factor"),
]
