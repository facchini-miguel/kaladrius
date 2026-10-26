from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    name = "apps.auditoria"
    label = "auditoria"
    verbose_name = "Auditoria"

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
