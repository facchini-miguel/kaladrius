from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="home"),
    path("clinic/register/", views.cadastrar_clinica, name="register_clinic"),
    path("account/password/", views.TrocarSenhaView.as_view(), name="change_password"),
    path("clinic/settings/", views.configuracoes, name="clinic_settings"),
    path("account/language/", views.trocar_idioma, name="change_language"),
]
