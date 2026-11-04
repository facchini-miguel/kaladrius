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
from django.db.models import F
from django.utils import timezone
from faker import Faker

from apps.audit.models import AuditEntry
from apps.audit.record import nome_do_modelo, registrar
from apps.core import fake_data
from apps.core.isolation import sem_isolamento
from apps.core.models import Clinic
from apps.core.validators import somente_digitos
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

OBSERVACOES = [
    "Prefere horários pela manhã.",
    "Avisar por telefone um dia antes da consulta.",
    "Paciente ansioso: explicar cada etapa do tratamento.",
    "Alergia a dipirona.",
    "Usa aparelho ortodôntico.",
    "Hipertenso, em acompanhamento médico.",
    "Retorno combinado para revisão semestral.",
]
RECHAMADAS = [
    "Revisão semestral",
    "Retorno",
    "Limpeza",
    "Manutenção do aparelho",
    "Avaliação",
    "Remover pontos",
]
DESLOCAMENTO_NASCIMENTO = 180  # days, either way: ages stay about the same


class ClinicaNaoEncontrada(Exception):
    pass


@dataclass
class Resultado:
    pacientes: int = 0
    agendamentos: int = 0
    rechamadas: int = 0
    profissionais: int = 0
    registros_apagados: int = 0


def _mesmo_tamanho(value, fake):
    """Fake digits like the original, keeping the area code (DDD) of phones.

    A mobile stays a mobile with the ninth digit (DDD + 9 + 8 digits) and a landline starts
    with 2 to 5, as in Anatel's plan: random digits made "mobiles" with 8 digits that
    WhatsApp links cannot open.
    """
    digitos = somente_digitos(value)
    if not digitos:
        return ""
    if len(digitos) < 10:
        return fake.numerify("#" * len(digitos))
    ddd = digitos[:2]
    if len(digitos) == 11 or digitos[2] in "6789":
        return f"{ddd}9{fake.numerify('########')}"
    return f"{ddd}{fake.random_int(2, 5)}{fake.numerify('#' * (len(digitos) - 3))}"


class _Anonimizador:
    def __init__(self, clinic, hoje):
        self.clinic = clinic
        self.hoje = hoje
        # System randomness: nothing about the original data can be derived from a seed.
        self.sorte = random.SystemRandom()
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(self.sorte.getrandbits(64))
        self.resultado = Resultado()

    def _nome(self, sex):
        return self.fake.name_female() if sex == "F" else self.fake.name_male()

    def _documento(self, patient, usados):
        if not patient.tax_id:
            return ""
        while True:
            gerar = fake_data.cnpj if patient.kind == Patient.Tipo.JURIDICA else fake_data.cpf
            documento = gerar(self.fake)
            if documento not in usados:
                usados.add(documento)
                return documento

    def _nascimento(self, date):
        if date is None:
            return None
        dias = self.sorte.randint(-DESLOCAMENTO_NASCIMENTO, DESLOCAMENTO_NASCIMENTO)
        return min(date + datetime.timedelta(days=dias), self.hoje)

    def pacientes(self):
        fake = self.fake
        pacientes = list(Patient.objects.filter(clinic=self.clinic))
        # Documents are cleared first, so a new fake one never collides with an old one
        # under the unique constraint.
        Patient.objects.filter(clinic=self.clinic).update(tax_id="")
        usados = set()
        for number, p in enumerate(pacientes, start=1):
            if p.kind == Patient.Tipo.JURIDICA:
                p.name = fake.company()[:200]
                p.legal_name = f"{p.name} Ltda."[:200] if p.legal_name else ""
            else:
                p.name = self._nome(p.sex)
            p.tax_id = self._documento(p, usados)
            p.rg = fake.numerify("#" * min(len(p.rg), 10)) if p.rg else ""
            p.state_registration = fake.numerify("#########") if p.state_registration else ""
            p.birth_date = self._nascimento(p.birth_date)
            p.occupation = fake_data.occupation(fake) if p.occupation else ""
            p.guardian = self._nome(self.sorte.choice("FM")) if p.guardian else ""
            p.home_phone = _mesmo_tamanho(p.home_phone, fake)
            p.work_phone = _mesmo_tamanho(p.work_phone, fake)
            mesmo_numero = p.whatsapp and p.whatsapp == p.mobile_phone
            p.mobile_phone = _mesmo_tamanho(p.mobile_phone, fake)
            p.whatsapp = p.mobile_phone if mesmo_numero else _mesmo_tamanho(p.whatsapp, fake)
            p.email = f"paciente{number}@example.com" if p.email else ""
            p.postal_code = (p.postal_code[:2] + fake.numerify("######")) if p.postal_code else ""
            p.neighborhood = fake.neighborhood()[:100] if p.neighborhood else ""
            p.street = fake.street_name()[:200] if p.street else ""
            p.number = fake.building_number()[:10] if p.number else ""
            p.complement = f"Apto {fake.random_int(1, 999)}" if p.complement else ""
            p.notes = self.sorte.choice(OBSERVACOES) if p.notes else ""
        campos = [
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
        Patient.objects.bulk_update(pacientes, campos, batch_size=500)
        self.resultado.pacientes = len(pacientes)
        return [p.name for p in pacientes if p.kind == Patient.Tipo.FISICA]

    def agendamentos(self, nomes):
        agendamentos = list(Appointment.objects.filter(clinic=self.clinic).select_related("kind"))
        for agendamento in agendamentos:
            # Blocked slots ("Ocupado") hold no personal data; the rest named the patient
            # and the procedure in free text.
            if agendamento.description and agendamento.description != agendamento.kind.name:
                name = self.sorte.choice(nomes) if nomes else self._nome(self.sorte.choice("FM"))
                agendamento.description = f"{name} - {agendamento.kind.name}"
        Appointment.objects.bulk_update(agendamentos, ["description"], batch_size=1000)
        self.resultado.agendamentos = len(agendamentos)

    def carteirinhas(self):
        """Card numbers and the plan holder's name identify a person; the plan stays."""
        carteirinhas = list(MemberCard.objects.filter(clinic=self.clinic))
        for carteirinha in carteirinhas:
            carteirinha.number = f"{carteirinha.pk:012d}"
            carteirinha.titular = self._nome(self.sorte.choice("FM")) if carteirinha.titular else ""
        MemberCard.objects.bulk_update(carteirinhas, ["number", "titular"], batch_size=500)

    def rechamadas(self):
        rechamadas = list(Recall.objects.filter(clinic=self.clinic))
        for rechamada in rechamadas:
            rechamada.description = self.sorte.choice(RECHAMADAS)
        Recall.objects.bulk_update(rechamadas, ["description"])
        self.resultado.rechamadas = len(rechamadas)

    def profissionais(self):
        profissionais = list(Practitioner.objects.filter(clinic=self.clinic))
        for practitioner in profissionais:
            sex = self.sorte.choice("FM")
            titulo = "Dra." if sex == "F" else "Dr."
            practitioner.name = f"{titulo} {self._nome(sex)}"
            if practitioner.registration:
                practitioner.registration = f"CRO {self.fake.numerify('#####')}"
        Practitioner.objects.bulk_update(profissionais, ["name", "registration"])
        self.resultado.profissionais = len(profissionais)

    def funcionarios(self):
        """Staff are people: name, CPF, phone and notes go. Salaries stay (no longer tied to
        a person), and the payables of their pay show the new names."""
        fake = self.fake
        funcionarios = list(Employee.objects.filter(clinic=self.clinic))
        for employee in funcionarios:
            employee.name = self._nome(self.sorte.choice("FM"))
            employee.cpf = ""
            employee.phone = _mesmo_tamanho(employee.phone, fake)
            employee.notes = ""
        Employee.objects.bulk_update(
            funcionarios, ["name", "cpf", "phone", "notes"], batch_size=500
        )
        Payroll.objects.filter(clinic=self.clinic).update(note="")
        for folha in (
            Payroll.objects.filter(clinic=self.clinic)
            .exclude(entry=None)
            .select_related("employee", "entry")
        ):
            Entry.objects.filter(pk=folha.entry_id).update(payer=folha.employee.name)

    def fornecedores(self):
        """A supplier who is a person is personal data; any supplier's contacts may be."""
        fake = self.fake
        fornecedores = list(Supplier.objects.filter(clinic=self.clinic))
        for number, f in enumerate(fornecedores, start=1):
            if f.kind == Supplier.Tipo.FISICA:
                f.name = self._nome(self.sorte.choice("FM"))
                f.legal_name = ""
                f.tax_id = ""
            f.phone = _mesmo_tamanho(f.phone, fake)
            f.whatsapp = _mesmo_tamanho(f.whatsapp, fake)
            f.email = f"fornecedor{number}@example.com" if f.email else ""
            f.notes = ""
        Supplier.objects.bulk_update(
            fornecedores,
            ["name", "legal_name", "tax_id", "phone", "whatsapp", "email", "notes"],
            batch_size=500,
        )

    def financeiro(self):
        """Free text of financial entries (payer, description, notes) may name people."""
        lancamentos = list(
            Entry.objects.filter(clinic=self.clinic).select_related("category", "supplier")
        )
        for entry in lancamentos:
            entry.description = entry.category.name
            if entry.supplier_id:
                entry.payer = entry.supplier.name
            else:
                entry.payer = self._nome(self.sorte.choice("FM")) if entry.payer else ""
            entry.notes = ""
        Entry.objects.bulk_update(lancamentos, ["description", "payer", "notes"], batch_size=500)
        Payment.objects.filter(clinic=self.clinic).update(note="", card_transaction_code="")
        CashRegister.objects.filter(clinic=self.clinic).update(note="")
        Estimate.objects.filter(clinic=self.clinic).update(notes="")
        CashMovement.objects.filter(clinic=self.clinic).update(reason="-")
        # Bank lines name who paid (Pix): keep only the bank's transaction type.
        BankTransaction.objects.filter(clinic=self.clinic).update(description=F("kind"), reason="")

    def auditoria(self):
        """Entries about these records held the original values: they go."""
        modelos = [
            nome_do_modelo(m)
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
        apagados, _ = AuditEntry.objects.filter(clinic=self.clinic, modelo__in=modelos).delete()
        # The import summary has no model but belongs to the same history.
        resumo, _ = AuditEntry.objects.filter(
            clinic=self.clinic, objeto_descricao__startswith="Importação do sistema antigo"
        ).delete()
        self.resultado.registros_apagados = apagados + resumo

    def executar(self):
        with transaction.atomic(), sem_isolamento():
            nomes = self.pacientes()
            self.agendamentos(nomes)
            self.fornecedores()
            self.financeiro()
            self.funcionarios()
            self.rechamadas()
            self.carteirinhas()
            self.profissionais()
            self.auditoria()
            r = self.resultado
            registrar(
                AuditEntry.Acao.ALTERAR,
                clinic=self.clinic,
                description=(
                    f"Dados anonimizados: {r.pacientes} pacientes, {r.agendamentos} agendamentos, "
                    f"{r.rechamadas} rechamadas, {r.profissionais} profissionais"
                ),
            )
        return self.resultado


def anonymize_clinic(nome_clinica, hoje=None):
    with sem_isolamento():
        clinic = Clinic.objects.filter(name=nome_clinica).first()
    if clinic is None:
        raise ClinicaNaoEncontrada(f"Clínica “{nome_clinica}” não encontrada.")
    return _Anonimizador(clinic, hoje or timezone.localdate()).executar()
