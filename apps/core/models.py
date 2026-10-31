import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from .isolamento import ModeloDaClinica


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
    # Public demo login (0.32.0, decision 085): its password is published, so it cannot
    # change it (nobody locks the others out) nor upload attachments (no file hosting).
    demonstracao = models.BooleanField(_("conta de demonstração"), default=False, editable=False)

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def save(self, *args, **kwargs):
        # A new person starts at the current version: "the system was updated" and forty
        # versions of history mean nothing to someone who just arrived (review, superuser).
        if self._state.adding and not self.ultima_versao_vista:
            from apps.novidades.releases import ReleasesInvalidas, versao_atual

            try:
                self.ultima_versao_vista = versao_atual()
            except ReleasesInvalidas:
                pass
        super().save(*args, **kwargs)


class Clinica(models.Model):
    """A clinic: the tenant that owns patients, schedules and the rest of the data."""

    INTERVALOS = [
        (10, _("10 minutos")),
        (15, _("15 minutos")),
        (20, _("20 minutos")),
        (30, _("30 minutos")),
        (60, _("1 hora")),
    ]

    class Area(models.TextChoices):
        """Primary area, kept for classification and the initial appointment types."""

        ODONTOLOGIA = "odontologia", _("Odontologia")
        MEDICINA = "medicina", _("Medicina")
        OUTRA = "outra", _("Outra área da saúde")

    nome = models.CharField(_("nome"), max_length=200)
    area = models.CharField(
        _("área principal"),
        max_length=20,
        choices=Area.choices,
        default=Area.ODONTOLOGIA,
        help_text=_(
            "Define os tipos iniciais de atendimento. As especialidades e os módulos são "
            "escolhidos abaixo e podem ser usados juntos."
        ),
    )
    documento = models.CharField(
        _("CPF/CNPJ"), max_length=14, blank=True, help_text=_("Somente números.")
    )
    email = models.EmailField(_("e-mail"), blank=True)
    telefone = models.CharField(_("telefone"), max_length=20, blank=True)
    endereco = models.CharField(
        _("endereço"),
        max_length=250,
        blank=True,
        help_text=_("Rua, número, bairro, cidade/UF e CEP, como sai no recibo."),
    )
    ativa = models.BooleanField(_("ativa"), default=True)
    exigir_duas_etapas = models.BooleanField(
        _("exigir verificação em duas etapas de quem acessa o prontuário ou o financeiro"),
        default=False,
        help_text=_(
            "Profissionais com prontuário, administradores e o financeiro só usam o sistema "
            "depois de ativar o código do aplicativo autenticador. A recepção não é obrigada."
        ),
    )
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

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Clinic creation and its initial capabilities/seeds succeed together.
        return super().save(*args, **kwargs)

    @property
    def odontologia(self):
        return self.modulo_habilitado(ModuloClinico.ODONTOLOGIA)

    @property
    def medicina(self):
        return self.modulo_habilitado(ModuloClinico.MEDICINA)

    def modulo_habilitado(self, codigo):
        # Explicit clinic filtering: this property is also used during clinic creation,
        # before a request has selected a clinic. Missing/unknown modules fail closed.
        if self.pk is None or codigo not in ModuloClinico.values:
            return False
        return ModuloDaClinica.todos.filter(clinica=self, codigo=codigo, ativo=True).exists()

    @classmethod
    def unica(cls):
        """The clinic of this installation (decision 069: one installation, one clinic)."""
        return cls.objects.filter(ativa=True).order_by("pk").first()


class ModuloClinico(models.TextChoices):
    """Parts of the system the clinic administrator turns on or off (decision 092).

    Patients, practitioners, the team, the base tables, the clinic settings and the audit
    log are the core: always on, so they are not listed here.
    """

    ODONTOLOGIA = "odontologia", _("Odontologia")
    MEDICINA = "medicina", _("Medicina")
    AGENDA = "agenda", _("Agenda")
    PRONTUARIO = "prontuario", _("Prontuário")
    ORCAMENTOS = "orcamentos", _("Orçamentos")
    FINANCEIRO = "financeiro", _("Financeiro")
    RECHAMADAS = "rechamadas", _("Rechamadas")
    ANIVERSARIANTES = "aniversariantes", _("Aniversariantes")
    CONVENIOS = "convenios", _("Convênios")
    PESSOAL = "pessoal", _("Pessoal")


ESPECIALIDADES = frozenset({ModuloClinico.ODONTOLOGIA, ModuloClinico.MEDICINA})
MODULOS_GERAIS = frozenset(ModuloClinico) - ESPECIALIDADES
# An approved estimate becomes a receivable and a month's pay becomes a payable, so both
# need finance turned on.
DEPENDENCIAS = {
    ModuloClinico.ORCAMENTOS: frozenset({ModuloClinico.FINANCEIRO}),
    ModuloClinico.PESSOAL: frozenset({ModuloClinico.FINANCEIRO}),
}


class ModuloDaClinica(ModeloDaClinica):
    codigo = models.CharField(_("módulo"), max_length=20, choices=ModuloClinico.choices)
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("módulo da clínica")
        verbose_name_plural = _("módulos da clínica")
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "codigo"], name="modulo_unico_por_clinica"),
            models.CheckConstraint(
                condition=models.Q(codigo__in=ModuloClinico.values),
                name="modulo_clinico_conhecido",
            ),
        ]

    def __str__(self):
        return self.get_codigo_display()


class Papel(models.TextChoices):
    """A user's role inside one clinic. Permissions per role live in permissoes.py."""

    ADMIN = "admin", _("Administrador da clínica")
    RECEPCAO = "recepcao", _("Recepção")
    PROFISSIONAL = "profissional", _("Profissional")
    # Finance only (0.35.0, decision 088): accounts, entries, cash desk, reports.
    FINANCEIRO = "financeiro", _("Financeiro")


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
