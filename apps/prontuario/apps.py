from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProntuarioConfig(AppConfig):
    name = "apps.prontuario"
    label = "prontuario"
    verbose_name = _("Prontuário")
