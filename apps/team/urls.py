from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("", views.member_list, name="list"),
    path("new/", views.new_member, name="new"),
    path("<int:pk>/edit/", views.edit_member, name="edit"),
    path("<int:pk>/password/", views.password, name="password"),
    path("<int:pk>/two-factor/", views.two_factor, name="two_factor"),
]
