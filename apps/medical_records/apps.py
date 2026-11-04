from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProntuarioConfig(AppConfig):
    name = "apps.medical_records"
    label = "prontuario"
    verbose_name = _("Prontuário")
