from django.urls import path

from . import views

app_name = "estimates"

urlpatterns = [
    path("", views.estimate_list, name="list"),
    path("new/", views.new_estimate, name="new"),
    path("<int:pk>/", views.estimate_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_estimate, name="edit"),
    path("<int:pk>/items/", views.add_item, name="item_add"),
    path("<int:pk>/items/<int:item>/remove/", views.remove_item, name="item_remove"),
    path("<int:pk>/discount/", views.discount, name="discount"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/decline/", views.refuse, name="decline"),
    path("<int:pk>/print/", views.print_estimate, name="print"),
    path("procedures/", views.procedures, name="procedures"),
    path("procedures/new/", views.procedure_form, name="procedure_new"),
    path("procedures/<int:pk>/", views.procedure_form, name="procedure_edit"),
]
