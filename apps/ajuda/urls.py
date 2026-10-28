from django.urls import path

from . import views

app_name = "ajuda"

# The help moved to the documentation site (decision 073); these addresses only redirect.
urlpatterns = [
    path("", views.para_o_site, name="indice"),
    path("tecnica/", views.para_o_site, {"caminho": ""}, name="tecnica_indice"),
    path("tecnica/<path:caminho>", views.para_o_site, name="tecnica"),
    path("<slug:pagina>/", views.para_o_site, name="manual"),
]
