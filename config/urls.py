from django.contrib import admin
from django.urls import include, path

from .api import api

admin.site.site_header = "Medical System: administração"
admin.site.site_title = "Medical System"
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    path("conta/", include("django.contrib.auth.urls")),
    path("novidades/", include("apps.novidades.urls")),
    path("", include("apps.core.urls")),
]
