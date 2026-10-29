"""The medical record (0.29.0, decision 081): one anamnesis per visit.

Written and read only by practitioners. Once finalized, a visit never changes: corrections
are addenda, with their own date and author. Nothing here is ever deleted (the record is
kept for 20 years), so patients with a medical record cannot be permanently deleted.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.agenda.models import Agendamento
from apps.core.isolamento import ModeloDaClinica
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

# The anamnesis fields, in the order they are written and shown.
CAMPOS_DA_ANAMNESE = ["queixa_principal", "historia", "antecedentes", "exame_fisico", "conduta"]


class Atendimento(ModeloDaClinica):
    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="atendimentos", verbose_name=_("paciente")
    )
    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.PROTECT,
        related_name="atendimentos",
        verbose_name=_("profissional"),
    )
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atendimento",
        verbose_name=_("agendamento"),
    )
    data = models.DateTimeField(_("data do atendimento"), default=timezone.now)
    queixa_principal = models.TextField(_("queixa principal"), blank=True)
    historia = models.TextField(_("história da doença atual"), blank=True)
    antecedentes = models.TextField(
        _("antecedentes"),
        blank=True,
        help_text=_("Pessoais e familiares, medicamentos em uso, alergias."),
    )
    exame_fisico = models.TextField(_("exame físico"), blank=True)
    conduta = models.TextField(_("conduta e plano"), blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    alterado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateTimeField(_("finalizado em"), null=True, blank=True)
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("atendimento")
        verbose_name_plural = _("atendimentos")
        ordering = ["-data", "-pk"]

    def __str__(self):
        return f"{self.paciente} – {timezone.localtime(self.data):%d/%m/%Y %H:%M}"

    @property
    def finalizado(self):
        return self.finalizado_em is not None


class Adendo(ModeloDaClinica):
    """A correction or note added to a finalized visit, which itself never changes."""

    atendimento = models.ForeignKey(
        Atendimento, on_delete=models.PROTECT, related_name="adendos", verbose_name=_("atendimento")
    )
    texto = models.TextField(_("adendo"))
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("adendo")
        verbose_name_plural = _("adendos")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {_('adendo')}"
