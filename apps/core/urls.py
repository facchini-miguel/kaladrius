from django.urls import path

from . import views

urlpatterns = [
    path("", views.start, name="home"),
    path("clinic/register/", views.register_clinic, name="register_clinic"),
    path("account/password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("clinic/settings/", views.clinic_settings, name="clinic_settings"),
    path("account/language/", views.change_language, name="change_language"),
]
