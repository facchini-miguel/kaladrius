from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext, pgettext, pgettext_lazy
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

# The default names are saved in Portuguese and shown in the user's language (see
# TipoAtendimento.nome_exibido). This list only marks them for makemessages; it is never read.
_DEFAULT_NAMES_FOR_TRANSLATION = [
    pgettext_lazy("tipo de atendimento", "Liberado"),
    pgettext_lazy("tipo de atendimento", "Consulta"),
    pgettext_lazy("tipo de atendimento", "Retorno"),
    pgettext_lazy("tipo de atendimento", "Exame"),
    pgettext_lazy("tipo de atendimento", "Procedimento"),
    pgettext_lazy("tipo de atendimento", "Atendimento de 15 em 15"),
    pgettext_lazy("tipo de atendimento", "Ocupado"),
    pgettext_lazy("tipo de atendimento", "Cirurgia"),
    pgettext_lazy("tipo de atendimento", "Dentística"),
    pgettext_lazy("tipo de atendimento", "Periodontia"),
    pgettext_lazy("tipo de atendimento", "Consulta inicial"),
    pgettext_lazy("tipo de atendimento", "Prótese"),
    pgettext_lazy("tipo de atendimento", "Endodontia"),
    pgettext_lazy("tipo de atendimento", "Ortodontia"),
]


class AppointmentType(ClinicModel):
    """Kind of appointment (surgery, first visit...). Its color paints the schedule."""

    name = models.CharField(_("nome"), max_length=60, db_collation=ALPHABETICAL)
    color = models.CharField(_("cor"), max_length=7, default="#0d6efd", validators=[validate_color])
    active = models.BooleanField(_("ativo"), default=True)

    class Meta:
        db_table = "schedule_appointment_type"
        verbose_name = _("tipo de atendimento")
        verbose_name_plural = _("tipos de atendimento")
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
        return pgettext("tipo de atendimento", self.name)


class TsTzRange(models.Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Appointment(ClinicModel):
    """An appointment in a practitioner's schedule."""

    class Status(models.TextChoices):
        """Whether the patient came (0.24.0). Only appointments with a patient are marked."""

        BOOKED = "agendado", _("Agendado")
        ATTENDED = "compareceu", _("Compareceu")
        MISSED = "faltou", _("Faltou")
        # Kept for the history and the no-show figures, but frees the time slot.
        CANCELLED = "desmarcou", _("Desmarcou")

    practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("profissional"),
    )
    kind = models.ForeignKey(
        AppointmentType,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("tipo de atendimento"),
    )
    start = models.DateTimeField(_("início"))
    end = models.DateTimeField(_("fim"))
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("paciente"),
    )
    description = models.TextField(_("descrição"), blank=True)
    status = models.CharField(
        _("situação"),
        max_length=10,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    # Appointments created together by "repeat N weeks" share the same series id.
    series = models.UUIDField(_("série"), null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "schedule_appointment"
        verbose_name = _("agendamento")
        verbose_name_plural = _("agendamentos")
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
                    status__in=spellings("schedule.Appointment.status", "desmarcou")
                ),
                violation_error_message=_("O profissional já tem um agendamento neste horário."),
            ),
        ]

    def __str__(self):
        return f"{self.title} ({timezone.localtime(self.start):%d/%m/%Y %H:%M})"

    @property
    def title(self):
        if self.patient_id:
            return self.patient.name
        return (self.description.strip().splitlines() or [gettext("Horário reservado")])[0]

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
