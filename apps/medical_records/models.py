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
        related_name="atendimentos",
        verbose_name=_("paciente"),
        db_column="paciente_id",
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="atendimentos",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit",
        verbose_name=_("agendamento"),
        db_column="agendamento_id",
    )
    date = models.DateTimeField(_("data do atendimento"), default=timezone.now, db_column="data")
    chief_complaint = models.TextField(
        _("queixa principal"), blank=True, db_column="queixa_principal"
    )
    present_illness = models.TextField(
        _("história da doença atual"), blank=True, db_column="historia"
    )
    medical_history = models.TextField(
        _("antecedentes"),
        blank=True,
        help_text=_("Pessoais e familiares, medicamentos em uso, alergias."),
        db_column="antecedentes",
    )
    physical_exam = models.TextField(_("exame físico"), blank=True, db_column="exame_fisico")
    plan = models.TextField(_("conduta e plano"), blank=True, db_column="conduta")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")
    finalized_at = models.DateTimeField(
        _("finalizado em"), null=True, blank=True, db_column="finalizado_em"
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("finalizado por"),
        db_column="finalizado_por_id",
    )

    class Meta:
        db_table = "prontuario_atendimento"
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
        related_name="adendos",
        verbose_name=_("atendimento"),
        db_column="atendimento_id",
    )
    text = models.TextField(_("adendo"), db_column="texto")
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "prontuario_adendo"
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
        related_name="atestados",
        verbose_name=_("atendimento"),
        db_column="atendimento_id",
    )
    kind = models.CharField(
        _("tipo"),
        max_length=20,
        choices=Kind.choices,
        default=Kind.ATTENDANCE,
        db_column="tipo",
    )
    date = models.DateField(_("data do atendimento"), default=timezone.localdate, db_column="data")
    start_time = models.TimeField(_("das"), null=True, blank=True, db_column="hora_inicio")
    end_time = models.TimeField(_("às"), null=True, blank=True, db_column="hora_fim")
    days = models.PositiveSmallIntegerField(
        _("dias de afastamento"),
        null=True,
        blank=True,
        help_text=_("Só para afastamento."),
        db_column="dias",
    )
    note = models.TextField(
        _("observações"),
        blank=True,
        help_text=_("Aparece no atestado. Por exemplo: deve permanecer em repouso."),
        db_column="observacao",
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "prontuario_atestado"
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
        related_name="receitas",
        verbose_name=_("atendimento"),
        db_column="atendimento_id",
    )
    medications = models.TextField(
        _("medicamentos e como usar"),
        help_text=_("Um item por linha: medicamento, dose e como usar."),
        db_column="prescricao",
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "prontuario_receita"
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
        related_name="pedidos_de_exames",
        verbose_name=_("atendimento"),
        db_column="atendimento_id",
    )
    exams = models.TextField(_("exames"), help_text=_("Um exame por linha."), db_column="exames")
    indication = models.TextField(
        _("indicação clínica"), blank=True, help_text=_("Aparece no pedido."), db_column="indicacao"
    )
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "prontuario_pedidodeexames"
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
        related_name="anexos",
        verbose_name=_("atendimento"),
        db_column="atendimento_id",
    )
    description = models.CharField(
        _("descrição"),
        max_length=200,
        blank=True,
        help_text=_("Por exemplo: hemograma de março."),
        db_column="descricao",
    )
    name = models.CharField(_("arquivo"), max_length=255, db_column="nome")
    kind = models.CharField(_("tipo"), max_length=50, db_column="tipo")
    size = models.PositiveIntegerField(_("tamanho"), db_column="tamanho")
    content = models.BinaryField(_("conteúdo"), db_column="conteudo")
    practitioner = models.ForeignKey(
        Practitioner,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("profissional"),
        db_column="profissional_id",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("criado por"),
        db_column="criado_por_id",
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "prontuario_anexo"
        verbose_name = _("anexo")
        verbose_name_plural = _("anexos")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.visit} – {self.description or self.name}"
