from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ReferenceDataConfig(AppConfig):
    name = "apps.reference_data"
    label = "reference_data"
    verbose_name = _("Tabelas de referência")
