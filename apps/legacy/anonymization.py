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


def _mesmo_tamanho(valor, fake):
    """Fake digits like the original, keeping the area code (DDD) of phones.

    A mobile stays a mobile with the ninth digit (DDD + 9 + 8 digits) and a landline starts
    with 2 to 5, as in Anatel's plan: random digits made "mobiles" with 8 digits that
    WhatsApp links cannot open.
    """
    digitos = somente_digitos(valor)
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

    def _nome(self, sexo):
        return self.fake.name_female() if sexo == "F" else self.fake.name_male()

    def _documento(self, patient, usados):
        if not patient.cpf_cnpj:
            return ""
        while True:
            gerar = fake_data.cnpj if patient.tipo == Patient.Tipo.JURIDICA else fake_data.cpf
            documento = gerar(self.fake)
            if documento not in usados:
                usados.add(documento)
                return documento

    def _nascimento(self, data):
        if data is None:
            return None
        dias = self.sorte.randint(-DESLOCAMENTO_NASCIMENTO, DESLOCAMENTO_NASCIMENTO)
        return min(data + datetime.timedelta(days=dias), self.hoje)

    def pacientes(self):
        fake = self.fake
        pacientes = list(Patient.objects.filter(clinic=self.clinic))
        # Documents are cleared first, so a new fake one never collides with an old one
        # under the unique constraint.
        Patient.objects.filter(clinic=self.clinic).update(cpf_cnpj="")
        usados = set()
        for number, p in enumerate(pacientes, start=1):
            if p.tipo == Patient.Tipo.JURIDICA:
                p.name = fake.company()[:200]
                p.razao_social = f"{p.name} Ltda."[:200] if p.razao_social else ""
            else:
                p.name = self._nome(p.sexo)
            p.cpf_cnpj = self._documento(p, usados)
            p.rg = fake.numerify("#" * min(len(p.rg), 10)) if p.rg else ""
            p.inscricao_estadual = fake.numerify("#########") if p.inscricao_estadual else ""
            p.data_nascimento = self._nascimento(p.data_nascimento)
            p.profissao = fake_data.profissao(fake) if p.profissao else ""
            p.responsavel = self._nome(self.sorte.choice("FM")) if p.responsavel else ""
            p.telefone_residencial = _mesmo_tamanho(p.telefone_residencial, fake)
            p.telefone_comercial = _mesmo_tamanho(p.telefone_comercial, fake)
            mesmo_numero = p.whatsapp and p.whatsapp == p.telefone_celular
            p.telefone_celular = _mesmo_tamanho(p.telefone_celular, fake)
            p.whatsapp = p.telefone_celular if mesmo_numero else _mesmo_tamanho(p.whatsapp, fake)
            p.email = f"paciente{number}@example.com" if p.email else ""
            p.cep = (p.cep[:2] + fake.numerify("######")) if p.cep else ""
            p.bairro = fake.bairro()[:100] if p.bairro else ""
            p.logradouro = fake.street_name()[:200] if p.logradouro else ""
            p.number = fake.building_number()[:10] if p.number else ""
            p.complemento = f"Apto {fake.random_int(1, 999)}" if p.complemento else ""
            p.notes = self.sorte.choice(OBSERVACOES) if p.notes else ""
        campos = [
            "name",
            "razao_social",
            "cpf_cnpj",
            "rg",
            "inscricao_estadual",
            "data_nascimento",
            "profissao",
            "responsavel",
            "telefone_residencial",
            "telefone_comercial",
            "telefone_celular",
            "whatsapp",
            "email",
            "cep",
            "bairro",
            "logradouro",
            "number",
            "complemento",
            "notes",
        ]
        Patient.objects.bulk_update(pacientes, campos, batch_size=500)
        self.resultado.pacientes = len(pacientes)
        return [p.name for p in pacientes if p.tipo == Patient.Tipo.FISICA]

    def agendamentos(self, nomes):
        agendamentos = list(Appointment.objects.filter(clinic=self.clinic).select_related("tipo"))
        for agendamento in agendamentos:
            # Blocked slots ("Ocupado") hold no personal data; the rest named the patient
            # and the procedure in free text.
            if agendamento.description and agendamento.description != agendamento.tipo.name:
                name = self.sorte.choice(nomes) if nomes else self._nome(self.sorte.choice("FM"))
                agendamento.description = f"{name} - {agendamento.tipo.name}"
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
            sexo = self.sorte.choice("FM")
            titulo = "Dra." if sexo == "F" else "Dr."
            practitioner.name = f"{titulo} {self._nome(sexo)}"
            if practitioner.registro:
                practitioner.registro = f"CRO {self.fake.numerify('#####')}"
        Practitioner.objects.bulk_update(profissionais, ["name", "registro"])
        self.resultado.profissionais = len(profissionais)

    def funcionarios(self):
        """Staff are people: name, CPF, phone and notes go. Salaries stay (no longer tied to
        a person), and the payables of their pay show the new names."""
        fake = self.fake
        funcionarios = list(Employee.objects.filter(clinic=self.clinic))
        for funcionario in funcionarios:
            funcionario.name = self._nome(self.sorte.choice("FM"))
            funcionario.cpf = ""
            funcionario.phone = _mesmo_tamanho(funcionario.phone, fake)
            funcionario.notes = ""
        Employee.objects.bulk_update(
            funcionarios, ["name", "cpf", "phone", "notes"], batch_size=500
        )
        Payroll.objects.filter(clinic=self.clinic).update(note="")
        for folha in (
            Payroll.objects.filter(clinic=self.clinic)
            .exclude(lancamento=None)
            .select_related("funcionario", "lancamento")
        ):
            Entry.objects.filter(pk=folha.lancamento_id).update(pessoa=folha.funcionario.name)

    def fornecedores(self):
        """A supplier who is a person is personal data; any supplier's contacts may be."""
        fake = self.fake
        fornecedores = list(Supplier.objects.filter(clinic=self.clinic))
        for number, f in enumerate(fornecedores, start=1):
            if f.tipo == Supplier.Tipo.FISICA:
                f.name = self._nome(self.sorte.choice("FM"))
                f.razao_social = ""
                f.cpf_cnpj = ""
            f.phone = _mesmo_tamanho(f.phone, fake)
            f.whatsapp = _mesmo_tamanho(f.whatsapp, fake)
            f.email = f"fornecedor{number}@example.com" if f.email else ""
            f.notes = ""
        Supplier.objects.bulk_update(
            fornecedores,
            ["name", "razao_social", "cpf_cnpj", "phone", "whatsapp", "email", "notes"],
            batch_size=500,
        )

    def financeiro(self):
        """Free text of financial entries (payer, description, notes) may name people."""
        lancamentos = list(
            Entry.objects.filter(clinic=self.clinic).select_related("categoria", "fornecedor")
        )
        for lancamento in lancamentos:
            lancamento.description = lancamento.categoria.name
            if lancamento.fornecedor_id:
                lancamento.pessoa = lancamento.fornecedor.name
            else:
                lancamento.pessoa = self._nome(self.sorte.choice("FM")) if lancamento.pessoa else ""
            lancamento.notes = ""
        Entry.objects.bulk_update(lancamentos, ["description", "pessoa", "notes"], batch_size=500)
        Payment.objects.filter(clinic=self.clinic).update(note="", cartao_codigo="")
        CashRegister.objects.filter(clinic=self.clinic).update(note="")
        Estimate.objects.filter(clinic=self.clinic).update(notes="")
        CashMovement.objects.filter(clinic=self.clinic).update(motivo="-")
        # Bank lines name who paid (Pix): keep only the bank's transaction type.
        BankTransaction.objects.filter(clinic=self.clinic).update(description=F("tipo"), motivo="")

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
