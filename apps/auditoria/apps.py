from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditoriaConfig(AppConfig):
    name = "apps.auditoria"
    label = "auditoria"
    verbose_name = _("Auditoria")

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
