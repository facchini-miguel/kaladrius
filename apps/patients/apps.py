from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PatientsConfig(AppConfig):
    name = "apps.patients"
    label = "patients"
    verbose_name = _("Pacientes")
