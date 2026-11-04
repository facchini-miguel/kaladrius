from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.account import views as conta_views
from apps.help import views as ajuda_views

from .api import api

admin.site.site_header = f"{settings.NOME_SISTEMA}: administração"
admin.site.site_title = settings.NOME_SISTEMA
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    # Login with a limit per address and two-step verification; password recovery by
    # e-mail where the installation has SMTP (apps.account, decision 111).
    path("conta/login/", conta_views.EntrarView.as_view(), name="login"),
    path("conta/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("conta/", include("apps.account.urls")),
    path("novidades/", include("apps.whats_new.urls")),
    path("profissionais/", include("apps.practitioners.urls")),
    path("referencias/", include("apps.reference_data.urls")),
    path("agenda/", include("apps.schedule.urls")),
    path("pacientes/", include("apps.patients.urls")),
    path("rechamadas/", include("apps.recalls.urls")),
    path("convenios/", include("apps.health_plans.urls")),
    path("pessoal/", include("apps.staff.urls")),
    path("auditoria/", include("apps.audit.urls")),
    path("equipe/", include("apps.team.urls")),
    path("ajuda/", include("apps.help.urls")),
    path("privacidade/", ajuda_views.privacidade, name="privacidade"),
    path("sistema/saude/", include("apps.monitoring.urls")),
    path("financeiro/", include("apps.finance.urls")),
    path("orcamentos/", include("apps.estimates.urls")),
    path("prontuario/", include("apps.medical_records.urls")),
    path("", include("apps.core.urls")),
]
