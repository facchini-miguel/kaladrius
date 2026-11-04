from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EquipeConfig(AppConfig):
    name = "apps.team"
    label = "equipe"
    verbose_name = _("Equipe")
