from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.results, name="list"),
    path("new/", views.new, name="new"),
    path("<int:pk>/", views.employee, name="employee"),
    path("<int:pk>/edit/", views.editar, name="edit"),
    path("payroll/", views.folha, name="payroll"),
]
