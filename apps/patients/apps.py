from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PacientesConfig(AppConfig):
    name = "apps.patients"
    label = "pacientes"
    verbose_name = _("Pacientes")
