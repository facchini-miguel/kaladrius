from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WhatsNewConfig(AppConfig):
    name = "apps.whats_new"
    label = "whats_new"
    verbose_name = _("What's new")
