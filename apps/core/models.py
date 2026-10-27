import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """System user.

    Custom model from day one so new fields can be added later without painful
    migrations. Access to clinics comes from Vinculo rows.
    """

    ultima_versao_vista = models.CharField(
        "última versão vista nas novidades", max_length=20, blank=True, editable=False
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"


class Clinica(models.Model):
    """A clinic: the tenant that owns patients, schedules and the rest of the data."""

    INTERVALOS = [
        (10, "10 minutos"),
        (15, "15 minutos"),
        (20, "20 minutos"),
        (30, "30 minutos"),
        (60, "1 hora"),
    ]

    nome = models.CharField("nome", max_length=200)
    documento = models.CharField(
        "CPF/CNPJ", max_length=14, blank=True, help_text="Somente números."
    )
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    ativa = models.BooleanField("ativa", default=True)
    agenda_inicio = models.TimeField("início da agenda", default=datetime.time(7, 30))
    agenda_fim = models.TimeField("fim da agenda", default=datetime.time(20, 0))
    agenda_intervalo = models.PositiveSmallIntegerField(
        "duração de cada horário", choices=INTERVALOS, default=30
    )
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    alterada_em = models.DateTimeField("alterada em", auto_now=True)

    class Meta:
        verbose_name = "clínica"
        verbose_name_plural = "clínicas"
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(agenda_inicio__lt=models.F("agenda_fim")),
                name="clinica_agenda_inicio_antes_do_fim",
                violation_error_message="O início da agenda deve ser antes do fim.",
            ),
        ]

    def __str__(self):
        return self.nome


class Papel(models.TextChoices):
    """A user's role inside one clinic. Permissions per role live in permissoes.py."""

    ADMIN = "admin", "Administrador da clínica"
    RECEPCAO = "recepcao", "Recepção"
    PROFISSIONAL = "profissional", "Profissional"


class Vinculo(models.Model):
    """Membership of a user in a clinic, with a role."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name="usuário",
    )
    clinica = models.ForeignKey(
        Clinica, on_delete=models.CASCADE, related_name="vinculos", verbose_name="clínica"
    )
    papel = models.CharField("perfil", max_length=20, choices=Papel.choices)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "vínculo com clínica"
        verbose_name_plural = "vínculos com clínicas"
        ordering = ["clinica__nome", "usuario__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "clinica"],
                name="vinculo_unico_por_clinica",
                violation_error_message="Este usuário já está vinculado a esta clínica.",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} em {self.clinica} ({self.get_papel_display()})"


class Backup(models.Model):
    """A database backup sent to Cloud Storage, recorded by deploy/servidor/backup.sh.

    Superusers see a warning in the web app when the newest one is too old, which is
    how a failing backup gets noticed (the server has no e-mail or paid alerting).
    """

    momento = models.DateTimeField("quando", auto_now_add=True, db_index=True)
    arquivo = models.CharField("arquivo", max_length=200)
    tamanho = models.PositiveBigIntegerField("tamanho (bytes)")

    class Meta:
        verbose_name = "backup"
        verbose_name_plural = "backups"
        ordering = ["-momento"]

    def __str__(self):
        return self.arquivo
