from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext, pgettext_lazy
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel, without_isolation
from apps.core.ordering import ALPHABETICAL
from apps.core.validators import validate_color
from apps.core.values import spellings
from apps.dentistry.teeth import APPOINTMENT_TYPES

# Appointment types a new clinic starts with (decision 080): the dental module's for the
# Odontologia area, these for the others. Each clinic can rename, recolor, deactivate or
# add types.
DEFAULT_TYPES = [
    ("Liberado", "#b9f1a7"),
    ("Consulta", "#e7a5f7"),
    ("Retorno", "#a7eef1"),
    ("Exame", "#f6f7a5"),
    ("Procedimento", "#f7a5a5"),
    ("Atendimento de 15 em 15", "#d5dae6"),
    ("Ocupado", "#a7bef1"),
]

# The default names are saved in Portuguese, as the clinic may rename them, and shown in the
# user's language (AppointmentType.display_name): their translations, by the saved name.
DEFAULT_NAMES = {
    "Liberado": pgettext_lazy("appointment type", "Available"),
    "Consulta": pgettext_lazy("appointment type", "Consultation"),
    "Retorno": pgettext_lazy("appointment type", "Follow-up"),
    "Exame": pgettext_lazy("appointment type", "Exam"),
    "Procedimento": pgettext_lazy("appointment type", "Procedure"),
    "Atendimento de 15 em 15": pgettext_lazy("appointment type", "15-minute appointments"),
    "Ocupado": pgettext_lazy("appointment type", "Busy"),
    "Cirurgia": pgettext_lazy("appointment type", "Surgery"),
    "Dentística": pgettext_lazy("appointment type", "Restorative dentistry"),
    "Periodontia": pgettext_lazy("appointment type", "Periodontics"),
    "Consulta inicial": pgettext_lazy("appointment type", "First visit"),
    "Prótese": pgettext_lazy("appointment type", "Prosthodontics"),
    "Endodontia": pgettext_lazy("appointment type", "Endodontics"),
    "Ortodontia": pgettext_lazy("appointment type", "Orthodontics"),
}


class AppointmentType(ClinicModel):
    """Kind of appointment (surgery, first visit...). Its color paints the schedule."""

    name = models.CharField(_("name"), max_length=60, db_collation=ALPHABETICAL)
    color = models.CharField(
        _("color"), max_length=7, default="#0d6efd", validators=[validate_color]
    )
    active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "schedule_appointment_type"
        verbose_name = _("appointment type")
        verbose_name_plural = _("appointment types")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "name"], name="appointment_type_unique"),
        ]

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        """The name in the user's language when it is one of the default types; a name the
        clinic typed itself (or renamed) has no translation and is shown as saved."""
        return str(DEFAULT_NAMES.get(self.name, self.name))


class TsTzRange(models.Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Appointment(ClinicModel):
    """An appointment in a practitioner's schedule."""

    class Status(models.TextChoices):
        """Whether the patient came (0.24.0). Only appointments with a patient are marked."""

        BOOKED = "booked", _("Booked")
        ATTENDED = "attended", _("Came")
        MISSED = "missed", _("Missed")
        # Kept for the history and the no-show figures, but frees the time slot.
        CANCELLED = "cancelled", pgettext_lazy("appointment", "Cancelled")

    practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("practitioner"),
    )
    kind = models.ForeignKey(
        AppointmentType,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("appointment type"),
    )
    start = models.DateTimeField(_("start"))
    end = models.DateTimeField(_("end"))
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("patient"),
    )
    description = models.TextField(_("description"), blank=True)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    # Appointments created together by "repeat N weeks" share the same series id.
    series = models.UUIDField(_("series"), null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "schedule_appointment"
        verbose_name = _("appointment")
        verbose_name_plural = _("appointments")
        ordering = ["start"]
        indexes = [
            models.Index(
                fields=["clinic", "practitioner", "start"], name="appointment_practitioner_start"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start__lt=models.F("end")),
                name="appointment_start_before_end",
            ),
            # Last line of defense against double booking, even under concurrent requests.
            ExclusionConstraint(
                name="appointment_no_overlap",
                expressions=[
                    (TsTzRange("start", "end", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("practitioner", RangeOperators.EQUAL),
                ],
                # A cancelled appointment does not hold the slot, in either spelling while the
                # stored values change (decision 197).
                condition=~models.Q(
                    status__in=spellings("schedule.Appointment.status", "cancelled")
                ),
                violation_error_message=_(
                    "The practitioner already has an appointment at this time."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.title} ({timezone.localtime(self.start):%d/%m/%Y %H:%M})"

    @property
    def title(self):
        if self.patient_id:
            return self.patient.name
        return (self.description.strip().splitlines() or [gettext("Reserved slot")])[0]

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def attendance_markable(self):
        """Came or missed can be marked from the day of the appointment on."""
        return timezone.localdate(self.start) <= timezone.localdate()


def create_default_types(clinic):
    """Create the default appointment types for a clinic that has none."""
    with without_isolation():
        if AppointmentType.objects.filter(clinic=clinic).exists():
            return
        appointment_types = (
            APPOINTMENT_TYPES if clinic.area == clinic.Area.DENTISTRY else DEFAULT_TYPES
        )
        AppointmentType.objects.bulk_create(
            AppointmentType(clinic=clinic, name=name, color=color)
            for name, color in appointment_types
        )
