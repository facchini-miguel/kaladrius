from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.ajuda import views as ajuda_views

from .api import api

admin.site.site_header = f"{settings.NOME_SISTEMA}: administração"
admin.site.site_title = settings.NOME_SISTEMA
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    # Only login and logout from django.contrib.auth: password reset needs e-mail, which
    # is not configured (users ask the clinic administrator for a new password instead).
    path("conta/login/", auth_views.LoginView.as_view(), name="login"),
    path("conta/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("novidades/", include("apps.novidades.urls")),
    path("profissionais/", include("apps.profissionais.urls")),
    path("referencias/", include("apps.referencias.urls")),
    path("agenda/", include("apps.agenda.urls")),
    path("pacientes/", include("apps.pacientes.urls")),
    path("rechamadas/", include("apps.rechamadas.urls")),
    path("auditoria/", include("apps.auditoria.urls")),
    path("equipe/", include("apps.equipe.urls")),
    path("ajuda/", include("apps.ajuda.urls")),
    path("privacidade/", ajuda_views.privacidade, name="privacidade"),
    path("sistema/saude/", include("apps.monitoramento.urls")),
    path("financeiro/", include("apps.financeiro.urls")),
    path("orcamentos/", include("apps.orcamentos.urls")),
    path("prontuario/", include("apps.prontuario.urls")),
    path("", include("apps.core.urls")),
]
