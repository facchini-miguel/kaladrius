from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProfissionaisConfig(AppConfig):
    name = "apps.profissionais"
    label = "profissionais"
    verbose_name = _("Profissionais")
