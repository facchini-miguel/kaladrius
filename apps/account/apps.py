from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountConfig(AppConfig):
    name = "apps.account"
    # The label the database knows this app by (its tables are conta_*): the folder was renamed
    # by decision 145 and, with no label of its own, the app was taken for a new one (decision 154).
    label = "account"
    verbose_name = _("Conta")
