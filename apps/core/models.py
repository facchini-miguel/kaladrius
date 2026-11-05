import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.dentistry.teeth import FDI, NUMBERINGS

from . import countries, currencies
from .isolation import ClinicModel


class User(AbstractUser):
    """System user.

    Custom model from day one so new fields can be added later without painful
    migrations. Access to clinics comes from Vinculo rows.
    """

    language = models.CharField(
        _("idioma"),
        max_length=10,
        choices=settings.LANGUAGES,
        blank=True,
        help_text=_("Vazio: o idioma do navegador."),
    )
    last_seen_version = models.CharField(
        _("última versão vista nas novidades"),
        max_length=20,
        blank=True,
        editable=False,
    )
    # Public demo login (0.32.0, decision 085): its password is published, so it cannot
    # change it (nobody locks the others out) nor upload attachments (no file hosting).
    demo = models.BooleanField(_("conta de demonstração"), default=False, editable=False)

    class Meta:
        db_table = "core_user"
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def save(self, *args, **kwargs):
        # A new person starts at the current version: "the system was updated" and forty
        # versions of history mean nothing to someone who just arrived (review, superuser).
        if self._state.adding and not self.last_seen_version:
            from apps.whats_new.releases import InvalidReleases, current_version

            try:
                self.last_seen_version = current_version()
            except InvalidReleases:
                pass
        super().save(*args, **kwargs)


class Clinic(models.Model):
    """A clinic: the tenant that owns patients, schedules and the rest of the data."""

    INTERVALS = [
        (10, _("10 minutos")),
        (15, _("15 minutos")),
        (20, _("20 minutos")),
        (30, _("30 minutos")),
        (60, _("1 hora")),
    ]

    class Area(models.TextChoices):
        """Primary area, kept for classification and the initial appointment types."""

        DENTISTRY = "odontologia", _("Odontologia")
        MEDICINE = "medicina", _("Medicina")
        OUTRA = "outra", _("Outra área da saúde")

    name = models.CharField(_("nome"), max_length=200)
    area = models.CharField(
        _("área principal"),
        max_length=20,
        choices=Area.choices,
        default=Area.DENTISTRY,
        help_text=_(
            "Define os tipos iniciais de atendimento. As especialidades e os módulos são "
            "escolhidos abaixo e podem ser usados juntos."
        ),
    )
    # The country's tax document, an individual's or a company's (decision 121).
    document = models.CharField(_("documento"), max_length=20, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("telefone"), max_length=20, blank=True)
    address = models.CharField(
        _("endereço"),
        max_length=250,
        blank=True,
        help_text=_("Rua, número, bairro, cidade/UF e CEP, como sai no recibo."),
    )
    currency = models.CharField(
        _("moeda"),
        max_length=3,
        choices=currencies.CHOICES,
        default=currencies.DEFAULT,
        help_text=_(
            "Em que moeda a clínica trabalha. Muda só como os valores aparecem, para toda a "
            "equipe e em qualquer idioma: nenhum valor já lançado é convertido."
        ),
    )
    country = models.CharField(
        _("país"),
        max_length=2,
        choices=countries.CHOICES,
        default=countries.DEFAULT,
        help_text=_(
            "Define o fuso horário disponível, o formato de telefones, códigos postais e "
            "datas em inglês, e a moeda sugerida."
        ),
    )
    time_zone = models.CharField(
        _("fuso horário"),
        max_length=40,
        choices=countries.TIME_ZONE_CHOICES,
        default=countries.DEFAULT_TIME_ZONE,
        help_text=_("Os horários da agenda e de todo o sistema seguem este fuso."),
    )
    tooth_numbering = models.CharField(
        _("numeração dos dentes"),
        max_length=10,
        choices=NUMBERINGS,
        default=FDI,
        help_text=_(
            "Como os dentes aparecem no odontograma e nos orçamentos. Muda só a exibição: os "
            "dentes já registrados continuam os mesmos."
        ),
    )
    active = models.BooleanField(_("ativa"), default=True)
    require_two_factor = models.BooleanField(
        _("exigir verificação em duas etapas de quem acessa o prontuário ou o financeiro"),
        default=False,
        help_text=_(
            "Profissionais com prontuário, administradores e o financeiro só usam o sistema "
            "depois de ativar o código do aplicativo autenticador. A recepção não é obrigada."
        ),
    )
    schedule_start = models.TimeField(_("início da agenda"), default=datetime.time(7, 30))
    schedule_end = models.TimeField(_("fim da agenda"), default=datetime.time(20, 0))
    schedule_interval = models.PositiveSmallIntegerField(
        _("duração de cada horário"), choices=INTERVALS, default=30
    )
    created_at = models.DateTimeField(_("criada em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterada em"), auto_now=True)

    class Meta:
        db_table = "core_clinic"
        verbose_name = _("clínica")
        verbose_name_plural = _("clínicas")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(schedule_start__lt=models.F("schedule_end")),
                name="clinic_schedule_start_before_end",
                violation_error_message=_("O início da agenda deve ser antes do fim."),
            ),
        ]

    def __str__(self):
        return self.name

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Clinic creation and its initial capabilities/seeds succeed together.
        return super().save(*args, **kwargs)

    @property
    def document_abbreviation(self):
        """The name of its document, in its country: "CNPJ", "EIN" (decision 121)."""
        from .identification import abbreviation

        return abbreviation(self.document, ("pessoa", "empresa"), self.country)

    @property
    def written_document(self):
        from .identification import write

        return write(self.document, ("pessoa", "empresa"), self.country)

    @property
    def dentistry(self):
        return self.module_enabled(ModuleCode.DENTISTRY)

    @property
    def medicine(self):
        return self.module_enabled(ModuleCode.MEDICINE)

    def module_enabled(self, code):
        # Explicit clinic filtering: this property is also used during clinic creation,
        # before a request has selected a clinic. Missing/unknown modules fail closed.
        if self.pk is None or code not in ModuleCode.values:
            return False
        return ClinicModule.all_objects.filter(clinic=self, code=code, active=True).exists()

    @classmethod
    def single(cls):
        """The clinic of this installation (decision 069: one installation, one clinic)."""
        return cls.objects.filter(active=True).order_by("pk").first()


class ModuleCode(models.TextChoices):
    """Parts of the system the clinic administrator turns on or off (decision 092).

    Patients, practitioners, the team, the base tables, the clinic settings and the audit
    log are the core: always on, so they are not listed here.
    """

    DENTISTRY = "odontologia", _("Odontologia")
    MEDICINE = "medicina", _("Medicina")
    SCHEDULE = "agenda", _("Agenda")
    MEDICAL_RECORDS = "prontuario", _("Prontuário")
    ESTIMATES = "orcamentos", _("Orçamentos")
    FINANCE = "financeiro", _("Financeiro")
    RECALLS = "rechamadas", _("Rechamadas")
    BIRTHDAYS = "aniversariantes", _("Aniversariantes")
    HEALTH_PLANS = "convenios", _("Convênios")
    STAFF = "pessoal", _("Pessoal")


SPECIALTIES = frozenset({ModuleCode.DENTISTRY, ModuleCode.MEDICINE})
GENERAL_MODULES = frozenset(ModuleCode) - SPECIALTIES
# An approved estimate becomes a receivable and a month's pay becomes a payable, so both
# need finance turned on.
DEPENDENCIES = {
    ModuleCode.ESTIMATES: frozenset({ModuleCode.FINANCE}),
    ModuleCode.STAFF: frozenset({ModuleCode.FINANCE}),
}


class ClinicModule(ClinicModel):
    code = models.CharField(_("módulo"), max_length=20, choices=ModuleCode.choices)
    active = models.BooleanField(_("ativo"), default=True)

    class Meta:
        db_table = "core_clinic_module"
        verbose_name = _("módulo da clínica")
        verbose_name_plural = _("módulos da clínica")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "code"], name="clinic_module_unique"),
            models.CheckConstraint(
                condition=models.Q(code__in=ModuleCode.values),
                name="clinic_module_known",
            ),
        ]

    def __str__(self):
        return self.get_code_display()


class Role(models.TextChoices):
    """A user's role inside one clinic. Permissions per role live in permissions.py."""

    ADMIN = "admin", _("Administrador da clínica")
    FRONT_DESK = "recepcao", _("Recepção")
    PRACTITIONER = "profissional", _("Profissional")
    # Finance only (0.35.0, decision 088): accounts, entries, cash desk, reports.
    FINANCE = "financeiro", _("Financeiro")


class Membership(models.Model):
    """Membership of a user in a clinic, with a role."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name=_("usuário"),
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="vinculos",
        verbose_name=_("clínica"),
    )
    role = models.CharField(_("perfil"), max_length=20, choices=Role.choices)
    active = models.BooleanField(_("ativo"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "core_membership"
        verbose_name = _("vínculo com clínica")
        verbose_name_plural = _("vínculos com clínicas")
        ordering = ["clinic__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "clinic"],
                name="membership_unique_per_clinic",
                violation_error_message=_("Este usuário já está vinculado a esta clínica."),
            ),
        ]

    def __str__(self):
        return f"{self.user} em {self.clinic} ({self.get_role_display()})"


class Backup(models.Model):
    """A database backup sent to Cloud Storage, recorded by deploy/server/backup.sh.

    Superusers see a warning in the web app when the newest one is too old, which is
    how a failing backup gets noticed (the server has no e-mail or paid alerting).
    """

    timestamp = models.DateTimeField(_("quando"), auto_now_add=True, db_index=True)
    file = models.CharField(_("arquivo"), max_length=200)
    size = models.PositiveBigIntegerField(_("tamanho (bytes)"))

    class Meta:
        verbose_name = _("backup")
        verbose_name_plural = _("backups")
        ordering = ["-timestamp"]

    def __str__(self):
        return self.file
