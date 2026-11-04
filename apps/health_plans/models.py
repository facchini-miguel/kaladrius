"""Health plans the clinic accepts and the patients' cards (decision 094).

Taken from the legacy Medical system (medical_convenios, medical_convenios_pessoas). This
first step is the register only: authorizations and billing the plan are another scope. What
each country registers, and how it is called, is in seguros.py (decision 125).
"""

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicaDiferente, ModeloDaClinica
from apps.core.ordering import ALFABETICA


class HealthPlan(ModeloDaClinica):
    nome = models.CharField(_("nome"), max_length=200, db_collation=ALFABETICA)
    # The insurer's registry in the clinic's country: the ANS in Brazil, the Payer ID in the
    # United States (seguros.py).
    registro = models.CharField(_("registro da operadora"), max_length=20, blank=True)
    telefone = models.CharField(_("telefone"), max_length=11, blank=True)
    observacoes = models.TextField(_("observações"), blank=True)
    ativo = models.BooleanField(_("ativo"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "convenios_convenio"
        verbose_name = _("convênio")
        verbose_name_plural = _("convênios")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                "clinic", Lower("nome"), name="convenio_nome_unico_por_clinica"
            ),
        ]

    def __str__(self):
        return self.nome


class MemberCard(ModeloDaClinica):
    """A patient's card of a health plan."""

    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        related_name="carteirinhas",
        verbose_name=_("paciente"),
        db_column="paciente_id",
    )
    convenio = models.ForeignKey(
        HealthPlan,
        on_delete=models.PROTECT,
        related_name="carteirinhas",
        verbose_name=_("convênio"),
    )
    plano = models.CharField(_("plano"), max_length=100, blank=True)
    numero = models.CharField(_("número da carteirinha"), max_length=30)
    # Only where the country's cards have them (seguros.py): the group or policy number of
    # North American cards, the patient's code on a family card.
    grupo = models.CharField(_("número do grupo"), max_length=30, blank=True)
    beneficiario = models.CharField(_("código do beneficiário"), max_length=10, blank=True)
    validade = models.DateField(_("validade"), null=True, blank=True)
    titular = models.CharField(
        _("titular"),
        max_length=200,
        blank=True,
        help_text=_("Se o paciente for dependente, o nome do titular do plano."),
    )
    ativa = models.BooleanField(_("ativa"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "convenios_carteirinha"
        verbose_name = _("carteirinha")
        verbose_name_plural = _("carteirinhas")
        ordering = ["-ativa", "convenio__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "convenio", "numero"], name="carteirinha_unica_por_convenio"
            ),
        ]

    def __str__(self):
        return f"{self.convenio} {self.numero}"

    def save(self, *args, **kwargs):
        # Having clinica_id on every row does not stop a link across clinics on its own.
        self._conferir_clinica()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.patient.clinic_id
        if {self.patient.clinic_id, self.convenio.clinic_id} != {self.clinic_id}:
            raise ClinicaDiferente("The patient and the health plan must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def vencida(self):
        return self.validade is not None and self.validade < timezone.localdate()
