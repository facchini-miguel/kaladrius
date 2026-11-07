"""Two-step verification with an authenticator app (decision 111).

The secret is shown once, as a QR code, when the person turns it on; the recovery codes are
shown once too and only their HMAC is kept, like a password.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy


class TwoFactor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor",
        verbose_name=_("user"),
    )
    secret = models.CharField(_("secret"), max_length=64, editable=False)
    active = models.BooleanField(pgettext_lazy("feminine", "active"), default=False)
    activated_at = models.DateTimeField(_("turned on at"), null=True, blank=True)
    # The last 30-second step accepted, so the same code cannot be used twice.
    last_step = models.BigIntegerField(_("last step"), default=0, editable=False)

    class Meta:
        db_table = "account_two_factor"
        verbose_name = _("two-step verification")
        verbose_name_plural = _("two-step verifications")

    def __str__(self):
        return str(self.user)


class RecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
        verbose_name=_("user"),
    )
    digest = models.CharField(_("digest"), max_length=64, editable=False)
    used_at = models.DateTimeField(_("used at"), null=True, blank=True)

    class Meta:
        db_table = "account_recovery_code"
        verbose_name = _("recovery code")
        verbose_name_plural = _("recovery codes")

    def __str__(self):
        return str(self.user)
