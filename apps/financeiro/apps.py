from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FinanceiroConfig(AppConfig):
    name = "apps.financeiro"
    label = "financeiro"
    verbose_name = _("Financeiro")

    def ready(self):
        from . import signals  # noqa: F401  (connects the signal handlers)
