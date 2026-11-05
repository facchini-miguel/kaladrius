from django.urls import path

from . import views

app_name = "help"

# The help moved to the documentation site (decision 073); these addresses only redirect.
urlpatterns = [
    path("", views.para_o_site, name="index"),
    path("technical/", views.para_o_site, {"path": ""}, name="technical_index"),
    path("technical/<path:path>", views.para_o_site, name="technical"),
    path("<slug:page>/", views.para_o_site, name="manual"),
]
