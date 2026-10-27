from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ModeloDaClinica
from apps.core.validadores import validar_cor


class Profissional(ModeloDaClinica):
    """A practitioner who sees patients (dentist, doctor, physiotherapist...)."""

    nome = models.CharField(_("nome"), max_length=200)
    registro = models.CharField(
        _("registro profissional"),
        max_length=30,
        blank=True,
        help_text=_("CRO, CRM, CREFITO, CRP…"),
    )
    cor = models.CharField(
        _("cor na agenda"), max_length=7, default="#0d6efd", validators=[validar_cor]
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profissionais",
        verbose_name=_("usuário de acesso"),
        help_text=_("Conta usada por este profissional para entrar no sistema (opcional)."),
    )
    ativo = models.BooleanField(_("ativo"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("profissional")
        verbose_name_plural = _("profissionais")
        ordering = ["nome"]
        indexes = [models.Index(fields=["clinica", "nome"], name="profissional_clinica_nome")]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "usuario"],
                condition=models.Q(usuario__isnull=False),
                name="profissional_usuario_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.nome
