from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EstimatesConfig(AppConfig):
    name = "apps.estimates"
    label = "estimates"
    verbose_name = _("Estimates")
