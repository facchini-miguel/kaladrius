from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OdontologiaConfig(AppConfig):
    name = "apps.dentistry"
    label = "odontologia"
    verbose_name = _("Odontologia")
