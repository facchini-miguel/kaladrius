from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ScheduleConfig(AppConfig):
    name = "apps.schedule"
    label = "schedule"
    verbose_name = _("Schedule")

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
