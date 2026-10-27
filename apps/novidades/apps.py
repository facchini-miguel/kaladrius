from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NovidadesConfig(AppConfig):
    name = "apps.novidades"
    label = "novidades"
    verbose_name = _("Novidades")
