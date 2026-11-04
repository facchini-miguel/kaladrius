from django.urls import path

from . import views

app_name = "help"

# The help moved to the documentation site (decision 073); these addresses only redirect.
urlpatterns = [
    path("", views.para_o_site, name="index"),
    path("technical/", views.para_o_site, {"caminho": ""}, name="technical_index"),
    path("technical/<path:caminho>", views.para_o_site, name="technical"),
    path("<slug:pagina>/", views.para_o_site, name="manual"),
]
