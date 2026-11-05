from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HealthPlansConfig(AppConfig):
    name = "apps.health_plans"
    label = "convenios"
    verbose_name = _("Convênios")
