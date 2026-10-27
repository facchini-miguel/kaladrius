import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Usuario(AbstractUser):
    """System user.

    Custom model from day one so new fields can be added later without painful
    migrations. Access to clinics comes from Vinculo rows.
    """

    idioma = models.CharField(
        _("idioma"),
        max_length=10,
        choices=settings.LANGUAGES,
        blank=True,
        help_text=_("Vazio: o idioma do navegador."),
    )
    ultima_versao_vista = models.CharField(
        _("última versão vista nas novidades"), max_length=20, blank=True, editable=False
    )

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")


class Clinica(models.Model):
    """A clinic: the tenant that owns patients, schedules and the rest of the data."""

    INTERVALOS = [
        (10, _("10 minutos")),
        (15, _("15 minutos")),
        (20, _("20 minutos")),
        (30, _("30 minutos")),
        (60, _("1 hora")),
    ]

    nome = models.CharField(_("nome"), max_length=200)
    documento = models.CharField(
        _("CPF/CNPJ"), max_length=14, blank=True, help_text=_("Somente números.")
    )
    email = models.EmailField(_("e-mail"), blank=True)
    telefone = models.CharField(_("telefone"), max_length=20, blank=True)
    ativa = models.BooleanField(_("ativa"), default=True)
    agenda_inicio = models.TimeField(_("início da agenda"), default=datetime.time(7, 30))
    agenda_fim = models.TimeField(_("fim da agenda"), default=datetime.time(20, 0))
    agenda_intervalo = models.PositiveSmallIntegerField(
        _("duração de cada horário"), choices=INTERVALOS, default=30
    )
    criada_em = models.DateTimeField(_("criada em"), auto_now_add=True)
    alterada_em = models.DateTimeField(_("alterada em"), auto_now=True)

    class Meta:
        verbose_name = _("clínica")
        verbose_name_plural = _("clínicas")
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(agenda_inicio__lt=models.F("agenda_fim")),
                name="clinica_agenda_inicio_antes_do_fim",
                violation_error_message=_("O início da agenda deve ser antes do fim."),
            ),
        ]

    def __str__(self):
        return self.nome


class Papel(models.TextChoices):
    """A user's role inside one clinic. Permissions per role live in permissoes.py."""

    ADMIN = "admin", _("Administrador da clínica")
    RECEPCAO = "recepcao", _("Recepção")
    PROFISSIONAL = "profissional", _("Profissional")


class Vinculo(models.Model):
    """Membership of a user in a clinic, with a role."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name=_("usuário"),
    )
    clinica = models.ForeignKey(
        Clinica, on_delete=models.CASCADE, related_name="vinculos", verbose_name=_("clínica")
    )
    papel = models.CharField(_("perfil"), max_length=20, choices=Papel.choices)
    ativo = models.BooleanField(_("ativo"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("vínculo com clínica")
        verbose_name_plural = _("vínculos com clínicas")
        ordering = ["clinica__nome", "usuario__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "clinica"],
                name="vinculo_unico_por_clinica",
                violation_error_message=_("Este usuário já está vinculado a esta clínica."),
            ),
        ]

    def __str__(self):
        return f"{self.usuario} em {self.clinica} ({self.get_papel_display()})"


class Backup(models.Model):
    """A database backup sent to Cloud Storage, recorded by deploy/servidor/backup.sh.

    Superusers see a warning in the web app when the newest one is too old, which is
    how a failing backup gets noticed (the server has no e-mail or paid alerting).
    """

    momento = models.DateTimeField(_("quando"), auto_now_add=True, db_index=True)
    arquivo = models.CharField(_("arquivo"), max_length=200)
    tamanho = models.PositiveBigIntegerField(_("tamanho (bytes)"))

    class Meta:
        verbose_name = _("backup")
        verbose_name_plural = _("backups")
        ordering = ["-momento"]

    def __str__(self):
        return self.arquivo
