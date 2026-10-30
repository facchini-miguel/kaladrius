from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PessoalConfig(AppConfig):
    name = "apps.pessoal"
    label = "pessoal"
    verbose_name = _("Pessoal")
