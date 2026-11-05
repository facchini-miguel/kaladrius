from django.urls import path

from . import views

app_name = "reference_data"

urlpatterns = [
    path("cities/", views.cities, name="cities"),
    path("cities/options/", views.city_options, name="city_options"),
    path("addresses/suggestions/", views.address_suggestions, name="address_suggestions"),
    path("banks/", views.banks, name="banks"),
]
