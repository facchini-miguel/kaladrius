"""Anonymization of a clinic's data, so real imported data can serve as test data (LGPD).

Personal data is replaced by fake values; the structure stays (number of records, dates
and times of the schedule, practitioners, appointment types, cities, ages, PF/PJ). The
replacement is random and keeps no link to the original values, so it cannot be undone
(LGPD, art. 12: anonymized data is not personal data).
"""

import datetime
import random
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from faker import Faker

from apps.audit import events
from apps.audit.models import AuditEntry
from apps.audit.record import log_event, model_label
from apps.core import fake_data
from apps.core.isolation import without_isolation
from apps.core.models import Clinic
from apps.core.validators import digits_only
from apps.estimates.models import Estimate
from apps.finance.models import (
    BankTransaction,
    CashMovement,
    CashRegister,
    Entry,
    Installment,
    Payment,
    Supplier,
)
from apps.health_plans.models import MemberCard
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule.models import Appointment
from apps.staff.models import Employee, Payroll

NOTES = [
    "Prefere horários pela manhã.",
    "Avisar por telefone um dia antes da consulta.",
    "Paciente ansioso: explicar cada etapa do tratamento.",
    "Alergia a dipirona.",
    "Usa aparelho ortodôntico.",
    "Hipertenso, em acompanhamento médico.",
    "Retorno combinado para revisão semestral.",
]
RECALLS = [
    "Revisão semestral",
    "Retorno",
    "Limpeza",
    "Manutenção do aparelho",
    "Avaliação",
    "Remover pontos",
]
BIRTH_DATE_SHIFT = 180  # days, either way: ages stay about the same


class ClinicNotFound(Exception):
    pass


@dataclass
class Result:
    patients: int = 0
    appointments: int = 0
    recalls: int = 0
    practitioners: int = 0
    deleted_records: int = 0


def _same_length(value, fake):
    """Fake digits like the original, keeping the area code (DDD) of phones.

    A mobile stays a mobile with the ninth digit (DDD + 9 + 8 digits) and a landline starts
    with 2 to 5, as in Anatel's plan: random digits made "mobiles" with 8 digits that
    WhatsApp links cannot open.
    """
    digits = digits_only(value)
    if not digits:
        return ""
    if len(digits) < 10:
        return fake.numerify("#" * len(digits))
    ddd = digits[:2]
    if len(digits) == 11 or digits[2] in "6789":
        return f"{ddd}9{fake.numerify('########')}"
    return f"{ddd}{fake.random_int(2, 5)}{fake.numerify('#' * (len(digits) - 3))}"


class _Anonymizer:
    def __init__(self, clinic, today):
        self.clinic = clinic
        self.today = today
        # System randomness: nothing about the original data can be derived from a seed.
        self.rng = random.SystemRandom()
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(self.rng.getrandbits(64))
        self.result = Result()

    def _name(self, sex):
        return self.fake.name_female() if sex == "F" else self.fake.name_male()

    def _document(self, patient, used):
        if not patient.tax_id:
            return ""
        while True:
            generate = fake_data.cnpj if patient.kind == Patient.Kind.COMPANY else fake_data.cpf
            document = generate(self.fake)
            if document not in used:
                used.add(document)
                return document

    def _birth_date(self, date):
        if date is None:
            return None
        days = self.rng.randint(-BIRTH_DATE_SHIFT, BIRTH_DATE_SHIFT)
        return min(date + datetime.timedelta(days=days), self.today)

    def patients(self):
        fake = self.fake
        patients = list(Patient.objects.filter(clinic=self.clinic))
        # Documents are cleared first, so a new fake one never collides with an old one
        # under the unique constraint.
        Patient.objects.filter(clinic=self.clinic).update(tax_id="")
        used = set()
        for number, p in enumerate(patients, start=1):
            if p.kind == Patient.Kind.COMPANY:
                p.name = fake.company()[:200]
                p.legal_name = f"{p.name} Ltda."[:200] if p.legal_name else ""
            else:
                p.name = self._name(p.sex)
            p.tax_id = self._document(p, used)
            p.rg = fake.numerify("#" * min(len(p.rg), 10)) if p.rg else ""
            p.state_registration = fake.numerify("#########") if p.state_registration else ""
            p.birth_date = self._birth_date(p.birth_date)
            p.occupation = fake_data.occupation(fake) if p.occupation else ""
            p.guardian = self._name(self.rng.choice("FM")) if p.guardian else ""
            p.home_phone = _same_length(p.home_phone, fake)
            p.work_phone = _same_length(p.work_phone, fake)
            same_number = p.whatsapp and p.whatsapp == p.mobile_phone
            p.mobile_phone = _same_length(p.mobile_phone, fake)
            p.whatsapp = p.mobile_phone if same_number else _same_length(p.whatsapp, fake)
            p.email = f"paciente{number}@example.com" if p.email else ""
            p.postal_code = (p.postal_code[:2] + fake.numerify("######")) if p.postal_code else ""
            p.neighborhood = fake.neighborhood()[:100] if p.neighborhood else ""
            p.street = fake.street_name()[:200] if p.street else ""
            p.number = fake.building_number()[:10] if p.number else ""
            p.complement = f"Apto {fake.random_int(1, 999)}" if p.complement else ""
            p.notes = self.rng.choice(NOTES) if p.notes else ""
        fields = [
            "name",
            "legal_name",
            "tax_id",
            "rg",
            "state_registration",
            "birth_date",
            "occupation",
            "guardian",
            "home_phone",
            "work_phone",
            "mobile_phone",
            "whatsapp",
            "email",
            "postal_code",
            "neighborhood",
            "street",
            "number",
            "complement",
            "notes",
        ]
        Patient.objects.bulk_update(patients, fields, batch_size=500)
        self.result.patients = len(patients)
        return [p.name for p in patients if p.kind == Patient.Kind.INDIVIDUAL]

    def appointments(self, names):
        appointments = list(Appointment.objects.filter(clinic=self.clinic).select_related("kind"))
        for appointment in appointments:
            # Blocked slots ("Ocupado") hold no personal data; the rest named the patient
            # and the procedure in free text.
            if appointment.description and appointment.description != appointment.kind.name:
                name = self.rng.choice(names) if names else self._name(self.rng.choice("FM"))
                appointment.description = f"{name} - {appointment.kind.name}"
        Appointment.objects.bulk_update(appointments, ["description"], batch_size=1000)
        self.result.appointments = len(appointments)

    def member_cards(self):
        """Card numbers and the plan holder's name identify a person; the plan stays."""
        member_cards = list(MemberCard.objects.filter(clinic=self.clinic))
        for member_card in member_cards:
            member_card.number = f"{member_card.pk:012d}"
            member_card.holder = self._name(self.rng.choice("FM")) if member_card.holder else ""
        MemberCard.objects.bulk_update(member_cards, ["number", "holder"], batch_size=500)

    def recalls(self):
        recalls = list(Recall.objects.filter(clinic=self.clinic))
        for recall in recalls:
            recall.description = self.rng.choice(RECALLS)
        Recall.objects.bulk_update(recalls, ["description"])
        self.result.recalls = len(recalls)

    def practitioners(self):
        practitioners = list(Practitioner.objects.filter(clinic=self.clinic))
        for practitioner in practitioners:
            sex = self.rng.choice("FM")
            title = "Dra." if sex == "F" else "Dr."
            practitioner.name = f"{title} {self._name(sex)}"
            if practitioner.registration:
                practitioner.registration = f"CRO {self.fake.numerify('#####')}"
        Practitioner.objects.bulk_update(practitioners, ["name", "registration"])
        self.result.practitioners = len(practitioners)

    def employees(self):
        """Staff are people: name, CPF, phone and notes go. Salaries stay (no longer tied to
        a person), and the payables of their pay show the new names."""
        fake = self.fake
        employees = list(Employee.objects.filter(clinic=self.clinic))
        for employee in employees:
            employee.name = self._name(self.rng.choice("FM"))
            employee.tax_id = ""
            employee.phone = _same_length(employee.phone, fake)
            employee.notes = ""
        Employee.objects.bulk_update(
            employees, ["name", "tax_id", "phone", "notes"], batch_size=500
        )
        Payroll.objects.filter(clinic=self.clinic).update(note="")
        for payroll in (
            Payroll.objects.filter(clinic=self.clinic)
            .exclude(entry=None)
            .select_related("employee", "entry")
        ):
            Entry.objects.filter(pk=payroll.entry_id).update(payer=payroll.employee.name)

    def suppliers(self):
        """A supplier who is a person is personal data; any supplier's contacts may be."""
        fake = self.fake
        suppliers = list(Supplier.objects.filter(clinic=self.clinic))
        for number, f in enumerate(suppliers, start=1):
            if f.kind == Supplier.Kind.INDIVIDUAL:
                f.name = self._name(self.rng.choice("FM"))
                f.legal_name = ""
                f.tax_id = ""
            f.phone = _same_length(f.phone, fake)
            f.whatsapp = _same_length(f.whatsapp, fake)
            f.email = f"fornecedor{number}@example.com" if f.email else ""
            f.notes = ""
        Supplier.objects.bulk_update(
            suppliers,
            ["name", "legal_name", "tax_id", "phone", "whatsapp", "email", "notes"],
            batch_size=500,
        )

    def finance(self):
        """Free text of financial entries (payer, description, notes) may name people."""
        entries = list(
            Entry.objects.filter(clinic=self.clinic).select_related("category", "supplier")
        )
        for entry in entries:
            entry.description = entry.category.name
            if entry.supplier_id:
                entry.payer = entry.supplier.name
            else:
                entry.payer = self._name(self.rng.choice("FM")) if entry.payer else ""
            entry.notes = ""
        Entry.objects.bulk_update(entries, ["description", "payer", "notes"], batch_size=500)
        Payment.objects.filter(clinic=self.clinic).update(note="", card_transaction_code="")
        CashRegister.objects.filter(clinic=self.clinic).update(note="")
        Estimate.objects.filter(clinic=self.clinic).update(notes="")
        CashMovement.objects.filter(clinic=self.clinic).update(reason="-")
        # Bank lines name who paid (Pix): keep only the bank's transaction type.
        BankTransaction.objects.filter(clinic=self.clinic).update(description=F("kind"), reason="")

    def audit(self):
        """Entries about these records held the original values: they go."""
        model_list = [
            model_label(m)
            for m in (
                Patient,
                Appointment,
                Recall,
                MemberCard,
                Employee,
                Practitioner,
                Entry,
                Installment,
                Payment,
                Estimate,
                BankTransaction,
                Supplier,
            )
        ]
        deleted_ones, _ = AuditEntry.objects.filter(
            clinic=self.clinic, model_name__in=model_list
        ).delete()
        # The import summary has no model but belongs to the same history.
        summary, _ = (
            AuditEntry.objects.filter(clinic=self.clinic)
            .filter(
                Q(event=events.LEGACY_IMPORT)
                # Written before decision 206.
                | Q(event="", object_repr__startswith="Importação do sistema antigo")
            )
            .delete()
        )
        self.result.deleted_records = deleted_ones + summary

    def run(self):
        with transaction.atomic(), without_isolation():
            names = self.patients()
            self.appointments(names)
            self.suppliers()
            self.finance()
            self.employees()
            self.recalls()
            self.member_cards()
            self.practitioners()
            self.audit()
            r = self.result
            log_event(
                AuditEntry.Action.CHANGE,
                clinic=self.clinic,
                event=events.LEGACY_ANONYMIZED,
                values={
                    "patients": r.patients,
                    "appointments": r.appointments,
                    "recalls": r.recalls,
                    "practitioners": r.practitioners,
                },
            )
        return self.result


def anonymize_clinic(clinic_name, today=None):
    with without_isolation():
        clinic = Clinic.objects.filter(name=clinic_name).first()
    if clinic is None:
        raise ClinicNotFound(f"Clinic “{clinic_name}” not found.")
    return _Anonymizer(clinic, today or timezone.localdate()).run()
