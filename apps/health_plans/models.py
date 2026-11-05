"""Health plans the clinic accepts and the patients' cards (decision 094).

Taken from the legacy Medical system (medical_convenios, medical_convenios_pessoas). This
first step is the register only: authorizations and billing the plan are another scope. What
each country registers, and how it is called, is in seguros.py (decision 125).
"""

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel, WrongClinic
from apps.core.ordering import ALPHABETICAL


class HealthPlan(ClinicModel):
    name = models.CharField(_("nome"), max_length=200, db_collation=ALPHABETICAL)
    # The insurer's registry in the clinic's country: the ANS in Brazil, the Payer ID in the
    # United States (seguros.py).
    registration = models.CharField(_("registro da operadora"), max_length=20, blank=True)
    phone = models.CharField(_("telefone"), max_length=11, blank=True)
    notes = models.TextField(_("observações"), blank=True)
    active = models.BooleanField(_("ativo"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "health_plans_health_plan"
        verbose_name = _("convênio")
        verbose_name_plural = _("convênios")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "clinic", Lower("name"), name="health_plan_name_unique_per_clinic"
            ),
        ]

    def __str__(self):
        return self.name


class MemberCard(ClinicModel):
    """A patient's card of a health plan."""

    patient = models.ForeignKey(
        "pacientes.Patient",
        on_delete=models.PROTECT,
        related_name="carteirinhas",
        verbose_name=_("paciente"),
    )
    health_plan = models.ForeignKey(
        HealthPlan,
        on_delete=models.PROTECT,
        related_name="carteirinhas",
        verbose_name=_("convênio"),
    )
    plan = models.CharField(_("plano"), max_length=100, blank=True)
    number = models.CharField(_("número da carteirinha"), max_length=30)
    # Only where the country's cards have them (seguros.py): the group or policy number of
    # North American cards, the patient's code on a family card.
    group = models.CharField(_("número do grupo"), max_length=30, blank=True)
    member_code = models.CharField(_("código do beneficiário"), max_length=10, blank=True)
    valid_until = models.DateField(_("validade"), null=True, blank=True)
    holder = models.CharField(
        _("titular"),
        max_length=200,
        blank=True,
        help_text=_("Se o paciente for dependente, o nome do titular do plano."),
    )
    active = models.BooleanField(_("ativa"), default=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "health_plans_member_card"
        verbose_name = _("carteirinha")
        verbose_name_plural = _("carteirinhas")
        ordering = ["-active", "health_plan__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "health_plan", "number"], name="member_card_unique_per_plan"
            ),
        ]

    def __str__(self):
        return f"{self.health_plan} {self.number}"

    def save(self, *args, **kwargs):
        # Having clinica_id on every row does not stop a link across clinics on its own.
        self._check_clinic()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.patient.clinic_id
        if {self.patient.clinic_id, self.health_plan.clinic_id} != {self.clinic_id}:
            raise WrongClinic("The patient and the health plan must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.valid_until is not None and self.valid_until < timezone.localdate()
