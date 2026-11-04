from django.urls import path

from . import views

app_name = "reference_data"

urlpatterns = [
    path("cities/", views.cidades, name="cities"),
    path("cities/options/", views.opcoes_cidades, name="city_options"),
    path("addresses/suggestions/", views.sugestoes_endereco, name="address_suggestions"),
    path("banks/", views.bancos, name="banks"),
]
