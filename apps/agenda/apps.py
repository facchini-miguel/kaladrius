from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AgendaConfig(AppConfig):
    name = "apps.agenda"
    label = "agenda"
    verbose_name = _("Agenda")

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
