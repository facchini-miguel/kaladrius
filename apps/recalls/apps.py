from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RechamadasConfig(AppConfig):
    name = "apps.recalls"
    label = "rechamadas"
    verbose_name = _("Rechamadas")
