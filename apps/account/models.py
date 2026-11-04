"""Two-step verification with an authenticator app (decision 111).

The secret is shown once, as a QR code, when the person turns it on; the recovery codes are
shown once too and only their HMAC is kept, like a password.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class DuasEtapas(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duas_etapas",
        verbose_name=_("usuário"),
    )
    segredo = models.CharField(_("segredo"), max_length=64, editable=False)
    ativa = models.BooleanField(_("ativa"), default=False)
    ativada_em = models.DateTimeField(_("ativada em"), null=True, blank=True)
    # The last 30-second step accepted, so the same code cannot be used twice.
    ultimo_passo = models.BigIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = _("verificação em duas etapas")
        verbose_name_plural = _("verificações em duas etapas")

    def __str__(self):
        return str(self.usuario)


class CodigoRecuperacao(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacao",
        verbose_name=_("usuário"),
    )
    resumo = models.CharField(max_length=64, editable=False)
    usado_em = models.DateTimeField(_("usado em"), null=True, blank=True)

    class Meta:
        verbose_name = _("código de recuperação")
        verbose_name_plural = _("códigos de recuperação")

    def __str__(self):
        return str(self.usuario)
