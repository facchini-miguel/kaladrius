import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicModel, WrongClinic
from apps.core.ordering import ALPHABETICAL


class Patient(ClinicModel):
    """A patient: an individual (CPF) or a company (CNPJ)."""

    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", _("Individual")
        COMPANY = "company", _("Company")

    class Sex(models.TextChoices):
        FEMALE = "F", _("Female")
        MALE = "M", _("Male")
        OTHER = "O", _("Other")

    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices, default=Kind.INDIVIDUAL)
    name = models.CharField(
        _("name"),
        max_length=200,
        help_text=_("For companies, the trade name."),
        db_collation=ALPHABETICAL,
    )
    legal_name = models.CharField(_("company name"), max_length=200, blank=True)
    # The country's document of an individual or a company (decision 121); the name stayed from
    # Brazil.
    tax_id = models.CharField(
        _("document"),
        max_length=20,
        blank=True,
        help_text=_("May be typed with or without punctuation."),
    )
    rg = models.CharField(_("ID card (RG)"), max_length=20, blank=True)
    state_registration = models.CharField(_("state registration"), max_length=20, blank=True)
    sex = models.CharField(_("sex"), max_length=1, choices=Sex.choices, blank=True)
    birth_date = models.DateField(_("birth date"), null=True, blank=True)
    marital_status = models.ForeignKey(
        "reference_data.MaritalStatus",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("marital status"),
    )
    occupation = models.CharField(_("occupation"), max_length=100, blank=True)
    guardian = models.CharField(
        _("guardian"),
        max_length=200,
        blank=True,
        help_text=_("For minors, for example."),
    )

    mobile_phone = models.CharField(_("mobile"), max_length=11, blank=True)
    # Fax and MSN from the legacy system are not kept as fields: nobody uses them anymore.
    whatsapp = models.CharField(
        _("WhatsApp"),
        max_length=11,
        blank=True,
        help_text=_("With the area code. The patient record opens the chat straight in WhatsApp."),
    )
    home_phone = models.CharField(_("home phone"), max_length=11, blank=True)
    work_phone = models.CharField(_("work phone"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)

    # Brazil: 8 digits; other countries (decision 117): up to a 9-digit ZIP+4.
    postal_code = models.CharField(_("Postal code (CEP)"), max_length=9, blank=True)
    state = models.ForeignKey(
        "reference_data.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("State"),
    )
    city = models.ForeignKey(
        "reference_data.City",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("city"),
    )
    # Outside Brazil the national state and city tables (IBGE) do not apply: typed text.
    state_name = models.CharField(_("state or province"), max_length=60, blank=True)
    city_name = models.CharField(_("city"), max_length=100, blank=True)
    neighborhood = models.CharField(_("district"), max_length=100, blank=True)
    street = models.CharField(
        _("address"),
        max_length=200,
        blank=True,
        help_text=_("Street, avenue…"),
    )
    number = models.CharField(_("number"), max_length=10, blank=True)
    complement = models.CharField(_("complement"), max_length=100, blank=True)

    notes = models.TextField(_("notes"), blank=True)
    active = models.BooleanField(_("active"), default=True)
    # Archiving replaces deleting: the patient leaves every screen of the team but keeps
    # their history (schedule, recalls, audit). Only clinic administrators see archived
    # patients, and can restore them (decision 046).
    archived = models.BooleanField(_("archived"), default=False)
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("archived by"),
    )
    created_at = models.DateTimeField(_("registered at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        db_table = "patients_patient"
        verbose_name = _("patient")
        verbose_name_plural = _("patients")
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
        return "company" if self.kind == self.Kind.COMPANY else "patient"

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
        MOTHER = "mother", _("Mother")
        FATHER = "father", _("Father")
        GUARDIAN = "guardian", _("Legal guardian")
        SPOUSE = "spouse", _("Spouse")
        CHILD = "child", _("Child")
        SIBLING = "sibling", _("Sibling")
        GRANDPARENT = "grandparent", _("Grandparent")
        GRANDCHILD = "grandchild", _("Grandchild")
        RELATIVE = "relative", _("Other relative")
        EMERGENCY = "emergency", _("Emergency contact")
        CONTACT = "contact", _("Contact")

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="related_people",
        verbose_name=_("patient"),
    )
    relationship = models.CharField(_("relationship"), max_length=20, choices=Relationship.choices)
    other_patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="related_to",
        verbose_name=_("clinic patient"),
    )
    name = models.CharField(_("name"), max_length=200, blank=True)
    phone = models.CharField(_("phone"), max_length=11, blank=True)
    note = models.CharField(_("note"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "patients_related_person"
        verbose_name = _("related person")
        verbose_name_plural = _("related people")
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
