from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LegadoConfig(AppConfig):
    name = "apps.legado"
    label = "legado"
    verbose_name = _("Importação do sistema antigo")
