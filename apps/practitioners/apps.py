from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PractitionersConfig(AppConfig):
    name = "apps.practitioners"
    label = "practitioners"
    verbose_name = _("Profissionais")
