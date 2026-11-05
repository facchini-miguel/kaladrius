from django.urls import path

from . import views

app_name = "account"

urlpatterns = [
    path("login/code/", views.code, name="code"),
    path("active/", views.active, name="active"),
    path("two-factor/", views.two_factor, name="two_factor"),
    path("password/forgot/", views.password_recover, name="recover"),
    path("password/forgot/sent/", views.password_recover_sent, name="recovery_sent"),
    path("password/new/<uidb64>/<token>/", views.new_password, name="new_password"),
    path("password/changed/", views.password_reset_done, name="password_changed"),
]
