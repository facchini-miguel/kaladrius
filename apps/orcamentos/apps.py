from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OrcamentosConfig(AppConfig):
    name = "apps.orcamentos"
    label = "orcamentos"
    verbose_name = _("Orçamentos")
