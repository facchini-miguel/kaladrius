from django.urls import path

from . import views

app_name = "health_plans"

urlpatterns = [
    path("", views.health_plan_list, name="list"),
    path("new/", views.new_health_plan, name="new"),
    path("<int:pk>/edit/", views.edit_health_plan, name="edit"),
    path("cards/new/<int:patient>/", views.new_member_card, name="card_new"),
    path("cards/<int:pk>/edit/", views.edit_member_card, name="card_edit"),
]
