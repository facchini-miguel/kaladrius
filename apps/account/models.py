"""Two-step verification with an authenticator app (decision 111).

The secret is shown once, as a QR code, when the person turns it on; the recovery codes are
shown once too and only their HMAC is kept, like a password.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TwoFactor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duas_etapas",
        verbose_name=_("usuário"),
        db_column="usuario_id",
    )
    secret = models.CharField(_("segredo"), max_length=64, editable=False, db_column="segredo")
    active = models.BooleanField(_("ativa"), default=False, db_column="ativa")
    activated_at = models.DateTimeField(
        _("ativada em"), null=True, blank=True, db_column="ativada_em"
    )
    # The last 30-second step accepted, so the same code cannot be used twice.
    last_step = models.BigIntegerField(
        _("último passo"), default=0, editable=False, db_column="ultimo_passo"
    )

    class Meta:
        db_table = "conta_duasetapas"
        verbose_name = _("verificação em duas etapas")
        verbose_name_plural = _("verificações em duas etapas")

    def __str__(self):
        return str(self.user)


class RecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacao",
        verbose_name=_("usuário"),
        db_column="usuario_id",
    )
    digest = models.CharField(_("resumo"), max_length=64, editable=False, db_column="resumo")
    used_at = models.DateTimeField(_("usado em"), null=True, blank=True, db_column="usado_em")

    class Meta:
        db_table = "conta_codigorecuperacao"
        verbose_name = _("código de recuperação")
        verbose_name_plural = _("códigos de recuperação")

    def __str__(self):
        return str(self.user)
