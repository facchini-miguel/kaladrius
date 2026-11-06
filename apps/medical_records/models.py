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
        verbose_name=_("paciente"),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="visits",
        verbose_name=_("profissional"),
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit",
        verbose_name=_("agendamento"),
    )
    date = models.DateTimeField(_("data do atendimento"), default=timezone.now)
    chief_complaint = models.TextField(_("queixa principal"), blank=True)
    present_illness = models.TextField(_("história da doença atual"), blank=True)
    medical_history = models.TextField(
        _("antecedentes"),
        blank=True,
        help_text=_("Pessoais e familiares, medicamentos em uso, alergias."),
    )
    physical_exam = models.TextField(_("exame físico"), blank=True)
    plan = models.TextField(_("conduta e plano"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)
    finalized_at = models.DateTimeField(_("finalizado em"), null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("finalizado por"),
    )

    class Meta:
        db_table = "medical_records_visit"
        verbose_name = _("atendimento")
        verbose_name_plural = _("atendimentos")
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
        verbose_name=_("atendimento"),
    )
    text = models.TextField(_("adendo"))
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_addendum"
        verbose_name = _("adendo")
        verbose_name_plural = _("adendos")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {_('adendo')}"


class Certificate(ClinicModel):
    """A medical certificate issued in a visit (0.30.0, decision 082). Never changed or
    deleted after issued; it can be printed again."""

    class Kind(models.TextChoices):
        ATTENDANCE = "comparecimento", _("Comparecimento")
        SICK_LEAVE = "afastamento", _("Afastamento")

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="certificates",
        verbose_name=_("atendimento"),
    )
    kind = models.CharField(
        _("tipo"),
        max_length=20,
        choices=Kind.choices,
        default=Kind.ATTENDANCE,
    )
    date = models.DateField(_("data do atendimento"), default=timezone.localdate)
    start_time = models.TimeField(_("das"), null=True, blank=True)
    end_time = models.TimeField(_("às"), null=True, blank=True)
    days = models.PositiveSmallIntegerField(
        _("dias de afastamento"),
        null=True,
        blank=True,
        help_text=_("Só para afastamento."),
    )
    note = models.TextField(
        _("observações"),
        blank=True,
        help_text=_("Aparece no atestado. Por exemplo: deve permanecer em repouso."),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_certificate"
        verbose_name = _("atestado")
        verbose_name_plural = _("atestados")
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
        verbose_name=_("atendimento"),
    )
    medications = models.TextField(
        _("medicamentos e como usar"),
        help_text=_("Um item por linha: medicamento, dose e como usar."),
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_prescription"
        # "Receita" is also revenue in Finance: a context keeps the translations apart.
        verbose_name = pgettext_lazy("prescrição", "receita")
        verbose_name_plural = pgettext_lazy("prescrição", "receitas")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {pgettext_lazy('prescrição', 'receita')}"


class ExamRequest(ClinicModel):
    """An exam request issued in a visit (0.31.0, decision 083): one exam per line."""

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="exam_requests",
        verbose_name=_("atendimento"),
    )
    exams = models.TextField(_("exames"), help_text=_("Um exame por linha."))
    indication = models.TextField(
        _("indicação clínica"), blank=True, help_text=_("Aparece no pedido.")
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_exam_request"
        verbose_name = _("pedido de exames")
        verbose_name_plural = _("pedidos de exames")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {_('pedido de exames')}"


class Attachment(ClinicModel):
    """A file kept in a visit: exam results, photos, reports (0.31.0, decision 083).

    Stored in the database, so the daily backup and the weekly restore test cover it, and
    only ever served through a view that checks the user is a practitioner.
    """

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name="attachments",
        verbose_name=_("atendimento"),
    )
    description = models.CharField(
        _("descrição"),
        max_length=200,
        blank=True,
        help_text=_("Por exemplo: hemograma de março."),
    )
    name = models.CharField(_("arquivo"), max_length=255)
    kind = models.CharField(_("tipo"), max_length=50)
    size = models.PositiveIntegerField(_("tamanho"))
    content = models.BinaryField(_("conteúdo"))
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "medical_records_attachment"
        verbose_name = _("anexo")
        verbose_name_plural = _("anexos")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {self.description or self.name}"
