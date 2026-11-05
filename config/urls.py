from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.account import views as conta_views
from apps.help import views as ajuda_views
from config import legacy_urls

from .api import api

admin.site.site_header = f"{settings.NOME_SISTEMA}: administração"
admin.site.site_title = settings.NOME_SISTEMA
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    # Login with a limit per address and two-step verification; password recovery by
    # e-mail where the installation has SMTP (apps.account, decision 111).
    path("account/login/", conta_views.ClinicLoginView.as_view(), name="login"),
    path("account/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/", include("apps.account.urls")),
    path("whats-new/", include("apps.whats_new.urls")),
    path("practitioners/", include("apps.practitioners.urls")),
    path("reference-data/", include("apps.reference_data.urls")),
    path("schedule/", include("apps.schedule.urls")),
    path("patients/", include("apps.patients.urls")),
    path("recalls/", include("apps.recalls.urls")),
    path("health-plans/", include("apps.health_plans.urls")),
    path("staff/", include("apps.staff.urls")),
    path("audit/", include("apps.audit.urls")),
    path("team/", include("apps.team.urls")),
    path("help/", include("apps.help.urls")),
    path("privacy/", ajuda_views.privacy, name="privacy"),
    path("system/health/", include("apps.monitoring.urls")),
    path("finance/", include("apps.finance.urls")),
    path("estimates/", include("apps.estimates.urls")),
    path("medical-records/", include("apps.medical_records.urls")),
    path("", include("apps.core.urls")),
]

# The addresses before decision 155, redirected to the English ones.
urlpatterns += legacy_urls.urlpatterns
