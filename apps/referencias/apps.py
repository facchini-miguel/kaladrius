from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReferenciasConfig(AppConfig):
    name = "apps.referencias"
    label = "referencias"
    verbose_name = _("Tabelas de referência")
