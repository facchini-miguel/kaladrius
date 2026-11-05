from django.urls import path

from . import views

urlpatterns = [
    path("", views.whats_new_list, name="whats_new"),
]
