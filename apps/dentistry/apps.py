from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DentistryConfig(AppConfig):
    name = "apps.dentistry"
    label = "dentistry"
    verbose_name = _("Dentistry")
