"""The medical record (0.29.0, decision 081): one anamnesis per visit.

Written and read only by practitioners. Once finalized, a visit never changes: corrections
are addenda, with their own date and author. Nothing here is ever deleted (the record is
kept for 20 years), so patients with a medical record cannot be permanently deleted.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.isolation import ClinicModel
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment

# The anamnesis fields, in the order they are written and shown.
ANAMNESIS_FIELDS = [
    "chief_complaint",
    "present_illness",
    "medical_history",
    "physical_exam",
    "plan",
]


class Visit(ClinicModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="visits",
        verbose_name=_("patient"),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="visits",
        verbose_name=_("practitioner"),
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit",
        verbose_name=_("appointment"),
    )
    date = models.DateTimeField(_("visit date"), default=timezone.now)
    chief_complaint = models.TextField(_("chief complaint"), blank=True)
    present_illness = models.TextField(_("history of present illness"), blank=True)
    medical_history = models.TextField(
        _("history"),
        blank=True,
        help_text=_("Personal and family, current medications, allergies."),
    )
    physical_exam = models.TextField(_("physical examination"), blank=True)
    plan = models.TextField(_("management and plan"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)
    finalized_at = models.DateTimeField(_("finalized on"), null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("finalized by"),
    )

    class Meta:
        db_table = "medical_records_visit"
        verbose_name = _("visit")
        verbose_name_plural = _("visits")
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.patient} – {timezone.localtime(self.date):%d/%m/%Y %H:%M}"

    @property
    def is_finalized(self):
        return self.finalized_at is not None


class Addendum(ClinicModel):
    """A correction or note added to a finalized visit, which itself never changes."""

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="addenda",
        verbose_name=_("visit"),
    )
    text = models.TextField(_("addendum"))
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_addendum"
        verbose_name = _("addendum")
        verbose_name_plural = _("addenda")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {_('addendum')}"


class Certificate(ClinicModel):
    """A medical certificate issued in a visit (0.30.0, decision 082). Never changed or
    deleted after issued; it can be printed again."""

    class Kind(models.TextChoices):
        ATTENDANCE = "attendance", _("Attendance")
        SICK_LEAVE = "sick_leave", _("Leave from activities")

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="certificates",
        verbose_name=_("visit"),
    )
    kind = models.CharField(
        _("type"),
        max_length=20,
        choices=Kind.choices,
        default=Kind.ATTENDANCE,
    )
    date = models.DateField(_("visit date"), default=timezone.localdate)
    start_time = models.TimeField(_("from"), null=True, blank=True)
    end_time = models.TimeField(_("to"), null=True, blank=True)
    days = models.PositiveSmallIntegerField(
        _("days of leave"),
        null=True,
        blank=True,
        help_text=_("Only for leave."),
    )
    note = models.TextField(
        _("notes"),
        blank=True,
        help_text=_("Appears on the certificate. For example: must stay at rest."),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_certificate"
        verbose_name = _("certificate")
        verbose_name_plural = _("certificates")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {self.get_kind_display()}"


class Prescription(ClinicModel):
    """A simple prescription issued in a visit (0.30.0, decision 082): free text, one item
    per line. Controlled drugs need the official forms, which the system does not issue."""

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="prescriptions",
        verbose_name=_("visit"),
    )
    medications = models.TextField(
        _("medicines and how to use them"),
        help_text=_("One item per line: medicine, dose and how to use it."),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_prescription"
        # "Receita" is also revenue in Finance: a context keeps the translations apart.
        verbose_name = pgettext_lazy("prescription", "prescription")
        verbose_name_plural = pgettext_lazy("prescription", "prescriptions")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {pgettext_lazy('prescription', 'prescription')}"


class ExamRequest(ClinicModel):
    """An exam request issued in a visit (0.31.0, decision 083): one exam per line."""

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="exam_requests",
        verbose_name=_("visit"),
    )
    exams = models.TextField(_("exams"), help_text=_("One exam per line."))
    indication = models.TextField(
        _("clinical indication"), blank=True, help_text=_("Appears on the request.")
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_exam_request"
        verbose_name = _("exam request")
        verbose_name_plural = _("exam requests")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {_('exam request')}"


class Attachment(ClinicModel):
    """A file kept in a visit: exam results, photos, reports (0.31.0, decision 083).

    Stored in the database, so the daily backup and the weekly restore test cover it, and
    only ever served through a view that checks the user is a practitioner.
    """

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="attachments",
        verbose_name=_("visit"),
    )
    description = models.CharField(
        _("description"),
        max_length=200,
        blank=True,
        help_text=_("For example: March blood count."),
    )
    name = models.CharField(_("file"), max_length=255)
    kind = models.CharField(_("type"), max_length=50)
    size = models.PositiveIntegerField(_("size"))
    content = models.BinaryField(_("content"))
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("practitioner"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_attachment"
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {self.description or self.name}"
