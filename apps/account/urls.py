from django.urls import path

from . import views

app_name = "account"

urlpatterns = [
    path("login/code/", views.code, name="code"),
    path("active/", views.active, name="active"),
    path("two-factor/", views.duas_etapas, name="two_factor"),
    path("password/forgot/", views.recuperar, name="recover"),
    path("password/forgot/sent/", views.recuperar_enviado, name="recovery_sent"),
    path("password/new/<uidb64>/<token>/", views.nova_senha, name="new_password"),
    path("password/changed/", views.senha_redefinida, name="password_changed"),
]
