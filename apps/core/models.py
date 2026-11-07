import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.dentistry.teeth import FDI, NUMBERINGS

from . import countries, currencies
from .isolation import ClinicModel
from .values import both_spellings


class User(AbstractUser):
    """System user.

    Custom model from day one so new fields can be added later without painful
    migrations. Access to clinics comes from Vinculo rows.
    """

    language = models.CharField(
        _("language"),
        max_length=10,
        choices=settings.LANGUAGES,
        blank=True,
        help_text=_("Empty: the browser's language."),
    )
    last_seen_version = models.CharField(
        _("last version seen in What's new"),
        max_length=20,
        blank=True,
        editable=False,
    )
    # Public demo login (0.32.0, decision 085): its password is published, so it cannot
    # change it (nobody locks the others out) nor upload attachments (no file hosting).
    demo = models.BooleanField(_("demo account"), default=False, editable=False)

    class Meta:
        db_table = "core_user"
        verbose_name = _("user")
        verbose_name_plural = _("users")

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
        (10, _("10 minutes")),
        (15, _("15 minutes")),
        (20, _("20 minutes")),
        (30, _("30 minutes")),
        (60, _("1 hour")),
    ]

    class Area(models.TextChoices):
        """Primary area, kept for classification and the initial appointment types."""

        DENTISTRY = "dentistry", _("Dentistry")
        MEDICINE = "medicine", _("Medicine")
        OTHER = "other", _("Other health area")

    name = models.CharField(_("name"), max_length=200)
    area = models.CharField(
        _("primary area"),
        max_length=20,
        choices=Area.choices,
        default=Area.DENTISTRY,
        help_text=_(
            "Sets the initial appointment types. The specialties and the modules are chosen "
            "below and can be used together."
        ),
    )
    # The country's tax document, an individual's or a company's (decision 121).
    document = models.CharField(_("document"), max_length=20, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("phone"), max_length=20, blank=True)
    address = models.CharField(
        _("address"),
        max_length=250,
        blank=True,
        help_text=_(
            "Street, number, district, city/state and postal code, as printed on receipts."
        ),
    )
    currency = models.CharField(
        _("currency"),
        max_length=3,
        choices=currencies.CHOICES,
        default=currencies.DEFAULT,
        help_text=_(
            "The currency the clinic works in. It only changes how amounts are shown, for the "
            "whole team and in any language: no amount already entered is converted."
        ),
    )
    country = models.CharField(
        _("country"),
        max_length=2,
        choices=countries.CHOICES,
        default=countries.DEFAULT,
        help_text=_(
            "Sets the available time zones, the format of phones, postal codes and English "
            "dates, and the suggested currency."
        ),
    )
    time_zone = models.CharField(
        _("time zone"),
        max_length=40,
        choices=countries.TIME_ZONE_CHOICES,
        default=countries.DEFAULT_TIME_ZONE,
        help_text=_("The schedule and every time in the system follow this time zone."),
    )
    tooth_numbering = models.CharField(
        _("tooth numbering"),
        max_length=10,
        choices=NUMBERINGS,
        default=FDI,
        help_text=_(
            "How teeth appear on the dental chart and in estimates. It only changes the "
            "display: teeth already recorded stay the same."
        ),
    )
    active = models.BooleanField(pgettext_lazy("feminine", "active"), default=True)
    require_two_factor = models.BooleanField(
        _("require two-step verification from whoever reaches the medical record or finance"),
        default=False,
        help_text=_(
            "Practitioners with medical records, administrators and finance staff only use "
            "the system after turning on the authenticator app code. The front desk is not "
            "required."
        ),
    )
    schedule_start = models.TimeField(_("schedule start"), default=datetime.time(7, 30))
    schedule_end = models.TimeField(_("schedule end"), default=datetime.time(20, 0))
    schedule_interval = models.PositiveSmallIntegerField(
        _("length of each slot"), choices=INTERVALS, default=30
    )
    created_at = models.DateTimeField(pgettext_lazy("feminine", "created at"), auto_now_add=True)
    updated_at = models.DateTimeField(pgettext_lazy("feminine", "changed at"), auto_now=True)

    class Meta:
        db_table = "core_clinic"
        verbose_name = _("clinic")
        verbose_name_plural = _("clinics")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(schedule_start__lt=models.F("schedule_end")),
                name="clinic_schedule_start_before_end",
                violation_error_message=_("The schedule start must be before its end."),
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

        return abbreviation(self.document, ("person", "company"), self.country)

    @property
    def written_document(self):
        from .identification import write

        return write(self.document, ("person", "company"), self.country)

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

    DENTISTRY = "dentistry", _("Dentistry")
    MEDICINE = "medicine", _("Medicine")
    SCHEDULE = "schedule", _("Schedule")
    MEDICAL_RECORDS = "medical_records", _("Medical record")
    ESTIMATES = "estimates", _("Estimates")
    FINANCE = "finance", _("Finance")
    RECALLS = "recalls", _("Recalls")
    BIRTHDAYS = "birthdays", _("Birthdays")
    HEALTH_PLANS = "health_plans", _("Health plans")
    STAFF = "staff", _("Staff")


SPECIALTIES = frozenset({ModuleCode.DENTISTRY, ModuleCode.MEDICINE})
GENERAL_MODULES = frozenset(ModuleCode) - SPECIALTIES
# An approved estimate becomes a receivable and a month's pay becomes a payable, so both
# need finance turned on.
DEPENDENCIES = {
    ModuleCode.ESTIMATES: frozenset({ModuleCode.FINANCE}),
    ModuleCode.STAFF: frozenset({ModuleCode.FINANCE}),
}


class ClinicModule(ClinicModel):
    code = models.CharField(_("module"), max_length=20, choices=ModuleCode.choices)
    active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "core_clinic_module"
        verbose_name = _("clinic module")
        verbose_name_plural = _("clinic modules")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "code"], name="clinic_module_unique"),
            models.CheckConstraint(
                # Both spellings while the stored values change (decision 197).
                condition=models.Q(
                    code__in=both_spellings("core.ClinicModule.code", ModuleCode.values)
                ),
                name="clinic_module_known",
            ),
        ]

    def __str__(self):
        return self.get_code_display()


class Role(models.TextChoices):
    """A user's role inside one clinic. Permissions per role live in permissions.py."""

    ADMIN = "admin", _("Clinic administrator")
    FRONT_DESK = "front_desk", _("Front desk")
    PRACTITIONER = "practitioner", _("Practitioner")
    # Finance only (0.35.0, decision 088): accounts, entries, cash desk, reports.
    FINANCE = "finance", _("Finance")


class Membership(models.Model):
    """Membership of a user in a clinic, with a role."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("user"),
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("clinic"),
    )
    role = models.CharField(_("role"), max_length=20, choices=Role.choices)
    active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "core_membership"
        verbose_name = _("clinic membership")
        verbose_name_plural = _("clinic memberships")
        ordering = ["clinic__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "clinic"],
                name="membership_unique_per_clinic",
                violation_error_message=_("This user is already a member of this clinic."),
            ),
        ]

    def __str__(self):
        return f"{self.user} em {self.clinic} ({self.get_role_display()})"


class Backup(models.Model):
    """A database backup sent to Cloud Storage, recorded by deploy/server/backup.sh.

    Superusers see a warning in the web app when the newest one is too old, which is
    how a failing backup gets noticed (the server has no e-mail or paid alerting).
    """

    timestamp = models.DateTimeField(_("when"), auto_now_add=True, db_index=True)
    file = models.CharField(_("file"), max_length=200)
    size = models.PositiveBigIntegerField(_("size (bytes)"))

    class Meta:
        verbose_name = _("backup")
        verbose_name_plural = _("backups")
        ordering = ["-timestamp"]

    def __str__(self):
        return self.file
