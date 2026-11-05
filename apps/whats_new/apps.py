from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WhatsNewConfig(AppConfig):
    name = "apps.whats_new"
    label = "novidades"
    verbose_name = _("Novidades")
