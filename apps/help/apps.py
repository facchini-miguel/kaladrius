from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AjudaConfig(AppConfig):
    name = "apps.help"
    label = "ajuda"
    verbose_name = _("Ajuda")
