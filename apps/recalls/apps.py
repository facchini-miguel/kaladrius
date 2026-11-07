from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RecallsConfig(AppConfig):
    name = "apps.recalls"
    label = "recalls"
    verbose_name = _("Recalls")
