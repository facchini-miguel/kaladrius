from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EquipeConfig(AppConfig):
    name = "apps.equipe"
    label = "equipe"
    verbose_name = _("Equipe")
