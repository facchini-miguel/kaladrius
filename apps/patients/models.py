import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel, WrongClinic
from apps.core.ordering import ALPHABETICAL


class Patient(ClinicModel):
    """A patient: an individual (CPF) or a company (CNPJ)."""

    class Kind(models.TextChoices):
        INDIVIDUAL = "PF", _("Pessoa física")
        COMPANY = "PJ", _("Pessoa jurídica")

    class Sex(models.TextChoices):
        FEMALE = "F", _("Feminino")
        MALE = "M", _("Masculino")
        OTHER = "O", _("Outro")

    kind = models.CharField(_("tipo"), max_length=2, choices=Kind.choices, default=Kind.INDIVIDUAL)
    name = models.CharField(
        _("nome"),
        max_length=200,
        help_text=_("Para pessoa jurídica, o nome fantasia."),
        db_collation=ALPHABETICAL,
    )
    legal_name = models.CharField(_("razão social"), max_length=200, blank=True)
    # The country's document of an individual or a company (decision 121); the name stayed from
    # Brazil.
    tax_id = models.CharField(
        _("documento"),
        max_length=20,
        blank=True,
        help_text=_("Pode ser digitado com ou sem pontuação."),
    )
    rg = models.CharField(_("RG"), max_length=20, blank=True)
    state_registration = models.CharField(_("inscrição estadual"), max_length=20, blank=True)
    sex = models.CharField(_("sexo"), max_length=1, choices=Sex.choices, blank=True)
    birth_date = models.DateField(_("data de nascimento"), null=True, blank=True)
    marital_status = models.ForeignKey(
        "reference_data.MaritalStatus",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estado civil"),
    )
    occupation = models.CharField(_("profissão"), max_length=100, blank=True)
    guardian = models.CharField(
        _("responsável"),
        max_length=200,
        blank=True,
        help_text=_("Para menores de idade, por exemplo."),
    )

    mobile_phone = models.CharField(_("celular"), max_length=11, blank=True)
    # Fax and MSN from the legacy system are not kept as fields: nobody uses them anymore.
    whatsapp = models.CharField(
        _("WhatsApp"),
        max_length=11,
        blank=True,
        help_text=_("Com DDD. A ficha abre a conversa direto no WhatsApp."),
    )
    home_phone = models.CharField(_("telefone residencial"), max_length=11, blank=True)
    work_phone = models.CharField(_("telefone comercial"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)

    # Brazil: 8 digits; other countries (decision 117): up to a 9-digit ZIP+4.
    postal_code = models.CharField(_("CEP"), max_length=9, blank=True)
    state = models.ForeignKey(
        "reference_data.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("UF"),
    )
    city = models.ForeignKey(
        "reference_data.City",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cidade"),
    )
    # Outside Brazil the national state and city tables (IBGE) do not apply: typed text.
    state_name = models.CharField(_("estado ou província"), max_length=60, blank=True)
    city_name = models.CharField(_("cidade"), max_length=100, blank=True)
    neighborhood = models.CharField(_("bairro"), max_length=100, blank=True)
    street = models.CharField(
        _("endereço"),
        max_length=200,
        blank=True,
        help_text=_("Rua, avenida…"),
    )
    number = models.CharField(_("número"), max_length=10, blank=True)
    complement = models.CharField(_("complemento"), max_length=100, blank=True)

    notes = models.TextField(_("observações"), blank=True)
    active = models.BooleanField(_("ativo"), default=True)
    # Archiving replaces deleting: the patient leaves every screen of the team but keeps
    # their history (schedule, recalls, audit). Only clinic administrators see archived
    # patients, and can restore them (decision 046).
    archived = models.BooleanField(_("arquivado"), default=False)
    archived_at = models.DateTimeField(_("arquivado em"), null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("arquivado por"),
    )
    created_at = models.DateTimeField(_("cadastrado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        db_table = "patients_patient"
        verbose_name = _("paciente")
        verbose_name_plural = _("pacientes")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["clinic", "name"], name="patient_clinic_name"),
            models.Index(fields=["clinic", "tax_id"], name="patient_clinic_tax_id"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "tax_id"],
                condition=~models.Q(tax_id=""),
                name="patient_tax_id_unique_per_clinic",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def document_role(self):
        """Its document's role in apps/core/identification.py."""
        return "empresa" if self.kind == self.Kind.COMPANY else "paciente"

    @property
    def age(self):
        """Age in whole years, or None when the birth date is unknown."""
        if self.birth_date is None:
            return None
        today = datetime.date.today()
        birth_date = self.birth_date
        return (
            today.year
            - birth_date.year
            - ((today.month, today.day) < (birth_date.month, birth_date.day))
        )

    @property
    def city_state(self):
        """City and state as written on the record: from the national tables in Brazil, typed
        anywhere else (decision 117)."""
        if self.city_id:
            return f"{self.city.name}/{self.city.state.abbreviation}"
        return ", ".join(part for part in (self.city_name, self.state_name) if part)

    @property
    def main_phone(self):
        return self.mobile_phone or self.home_phone or self.work_phone


class RelatedPerson(ClinicModel):
    """A relative or contact of a patient (decision 101, legacy `id_pessoas_relac`).

    Either another patient of the clinic (the link then shows on both records) or someone
    outside it, kept with just a name and a phone. A link grants no access to anything:
    it is only information on the registration.
    """

    class Relationship(models.TextChoices):
        MOTHER = "mae", _("Mãe")
        FATHER = "pai", _("Pai")
        GUARDIAN = "responsavel", _("Responsável legal")
        SPOUSE = "conjuge", _("Cônjuge")
        CHILD = "filho", _("Filho(a)")
        SIBLING = "irmao", _("Irmão(ã)")
        GRANDPARENT = "avo", _("Avô/avó")
        GRANDCHILD = "neto", _("Neto(a)")
        RELATIVE = "parente", _("Outro parente")
        EMERGENCY = "emergencia", _("Contato de emergência")
        CONTACT = "contato", _("Contato")

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="related_people",
        verbose_name=_("paciente"),
    )
    relationship = models.CharField(_("vínculo"), max_length=20, choices=Relationship.choices)
    other_patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="related_to",
        verbose_name=_("paciente da clínica"),
    )
    name = models.CharField(_("nome"), max_length=200, blank=True)
    phone = models.CharField(_("telefone"), max_length=11, blank=True)
    note = models.CharField(_("observação"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        db_table = "patients_related_person"
        verbose_name = _("pessoa relacionada")
        verbose_name_plural = _("pessoas relacionadas")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(other_patient__isnull=False) | ~models.Q(name=""),
                name="related_person_patient_or_name",
            ),
            models.CheckConstraint(
                condition=~models.Q(other_patient=models.F("patient")),
                name="related_person_not_self",
            ),
            models.UniqueConstraint(
                fields=["patient", "other_patient", "relationship"],
                name="related_person_unique",
            ),
        ]

    def __str__(self):
        return f"{self.get_relationship_display()}: {self.display_name}"

    def save(self, *args, **kwargs):
        self._check_clinic()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.patient.clinic_id
        clinics = {self.patient.clinic_id}
        if self.other_patient_id:
            clinics.add(self.other_patient.clinic_id)
        if clinics != {self.clinic_id}:
            raise WrongClinic("Both patients must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.other_patient.name if self.other_patient_id else self.name

    @property
    def display_phone(self):
        if self.phone or not self.other_patient_id:
            return self.phone
        other = self.other_patient
        return other.whatsapp or other.mobile_phone or other.home_phone
