from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ConveniosConfig(AppConfig):
    name = "apps.convenios"
    label = "convenios"
    verbose_name = _("Convênios")
