from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ContaConfig(AppConfig):
    name = "apps.conta"
    verbose_name = _("Conta")
