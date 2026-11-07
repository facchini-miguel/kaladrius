from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HealthPlansConfig(AppConfig):
    name = "apps.health_plans"
    label = "health_plans"
    verbose_name = _("Health plans")
