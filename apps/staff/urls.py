from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.employee_list, name="list"),
    path("new/", views.new_employee, name="new"),
    path("<int:pk>/", views.employee, name="employee"),
    path("<int:pk>/edit/", views.edit_employee, name="edit"),
    path("payroll/", views.payroll, name="payroll"),
]
