from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = "apps.agenda"
    label = "agenda"
    verbose_name = "Agenda"

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
