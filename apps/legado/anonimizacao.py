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
from django.utils import timezone
from faker import Faker

from apps.agenda.models import Agendamento
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import nome_do_modelo, registrar
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica
from apps.core.validadores import somente_digitos
from apps.financeiro.models import Caixa, Lancamento, MovimentoCaixa, Pagamento, Parcela
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

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
    """Fake digits with the length of the original (keeping the area code of phones)."""
    digitos = somente_digitos(valor)
    if not digitos:
        return ""
    prefixo = digitos[:2] if len(digitos) >= 10 else ""
    return prefixo + fake.numerify("#" * (len(digitos) - len(prefixo)))


class _Anonimizador:
    def __init__(self, clinica, hoje):
        self.clinica = clinica
        self.hoje = hoje
        # System randomness: nothing about the original data can be derived from a seed.
        self.sorte = random.SystemRandom()
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(self.sorte.getrandbits(64))
        self.resultado = Resultado()

    def _nome(self, sexo):
        return self.fake.name_female() if sexo == "F" else self.fake.name_male()

    def _documento(self, paciente, usados):
        if not paciente.cpf_cnpj:
            return ""
        while True:
            gerar = self.fake.cnpj if paciente.tipo == Paciente.Tipo.JURIDICA else self.fake.cpf
            documento = somente_digitos(gerar())
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
        pacientes = list(Paciente.objects.filter(clinica=self.clinica))
        # Documents are cleared first, so a new fake one never collides with an old one
        # under the unique constraint.
        Paciente.objects.filter(clinica=self.clinica).update(cpf_cnpj="")
        usados = set()
        for numero, p in enumerate(pacientes, start=1):
            if p.tipo == Paciente.Tipo.JURIDICA:
                p.nome = fake.company()[:200]
                p.razao_social = f"{p.nome} Ltda."[:200] if p.razao_social else ""
            else:
                p.nome = self._nome(p.sexo)
            p.cpf_cnpj = self._documento(p, usados)
            p.rg = fake.numerify("#" * min(len(p.rg), 10)) if p.rg else ""
            p.inscricao_estadual = fake.numerify("#########") if p.inscricao_estadual else ""
            p.data_nascimento = self._nascimento(p.data_nascimento)
            p.profissao = fake.job()[:100] if p.profissao else ""
            p.responsavel = self._nome(self.sorte.choice("FM")) if p.responsavel else ""
            p.telefone_residencial = _mesmo_tamanho(p.telefone_residencial, fake)
            p.telefone_comercial = _mesmo_tamanho(p.telefone_comercial, fake)
            p.telefone_celular = _mesmo_tamanho(p.telefone_celular, fake)
            p.email = f"paciente{numero}@example.com" if p.email else ""
            p.cep = (p.cep[:2] + fake.numerify("######")) if p.cep else ""
            p.bairro = fake.bairro()[:100] if p.bairro else ""
            p.logradouro = fake.street_name()[:200] if p.logradouro else ""
            p.numero = fake.building_number()[:10] if p.numero else ""
            p.complemento = f"Apto {fake.random_int(1, 999)}" if p.complemento else ""
            p.observacoes = self.sorte.choice(OBSERVACOES) if p.observacoes else ""
        campos = [
            "nome",
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
            "email",
            "cep",
            "bairro",
            "logradouro",
            "numero",
            "complemento",
            "observacoes",
        ]
        Paciente.objects.bulk_update(pacientes, campos, batch_size=500)
        self.resultado.pacientes = len(pacientes)
        return [p.nome for p in pacientes if p.tipo == Paciente.Tipo.FISICA]

    def agendamentos(self, nomes):
        agendamentos = list(Agendamento.objects.filter(clinica=self.clinica).select_related("tipo"))
        for agendamento in agendamentos:
            # Blocked slots ("Ocupado") hold no personal data; the rest named the patient
            # and the procedure in free text.
            if agendamento.descricao and agendamento.descricao != agendamento.tipo.nome:
                nome = self.sorte.choice(nomes) if nomes else self._nome(self.sorte.choice("FM"))
                agendamento.descricao = f"{nome} - {agendamento.tipo.nome}"
        Agendamento.objects.bulk_update(agendamentos, ["descricao"], batch_size=1000)
        self.resultado.agendamentos = len(agendamentos)

    def rechamadas(self):
        rechamadas = list(Rechamada.objects.filter(clinica=self.clinica))
        for rechamada in rechamadas:
            rechamada.descricao = self.sorte.choice(RECHAMADAS)
        Rechamada.objects.bulk_update(rechamadas, ["descricao"])
        self.resultado.rechamadas = len(rechamadas)

    def profissionais(self):
        profissionais = list(Profissional.objects.filter(clinica=self.clinica))
        for profissional in profissionais:
            sexo = self.sorte.choice("FM")
            titulo = "Dra." if sexo == "F" else "Dr."
            profissional.nome = f"{titulo} {self._nome(sexo)}"
            if profissional.registro:
                profissional.registro = f"CRO {self.fake.numerify('#####')}"
        Profissional.objects.bulk_update(profissionais, ["nome", "registro"])
        self.resultado.profissionais = len(profissionais)

    def financeiro(self):
        """Free text of financial entries (payer, description, notes) may name people."""
        lancamentos = list(
            Lancamento.objects.filter(clinica=self.clinica).select_related("categoria")
        )
        for lancamento in lancamentos:
            lancamento.descricao = lancamento.categoria.nome
            lancamento.pessoa = self._nome(self.sorte.choice("FM")) if lancamento.pessoa else ""
            lancamento.observacoes = ""
        Lancamento.objects.bulk_update(
            lancamentos, ["descricao", "pessoa", "observacoes"], batch_size=500
        )
        Pagamento.objects.filter(clinica=self.clinica).update(observacao="", cartao_codigo="")
        Caixa.objects.filter(clinica=self.clinica).update(observacao="")
        MovimentoCaixa.objects.filter(clinica=self.clinica).update(motivo="-")

    def auditoria(self):
        """Entries about these records held the original values: they go."""
        modelos = [
            nome_do_modelo(m)
            for m in (
                Paciente,
                Agendamento,
                Rechamada,
                Profissional,
                Lancamento,
                Parcela,
                Pagamento,
            )
        ]
        apagados, _ = RegistroAuditoria.objects.filter(
            clinica=self.clinica, modelo__in=modelos
        ).delete()
        # The import summary has no model but belongs to the same history.
        resumo, _ = RegistroAuditoria.objects.filter(
            clinica=self.clinica, objeto_descricao__startswith="Importação do sistema antigo"
        ).delete()
        self.resultado.registros_apagados = apagados + resumo

    def executar(self):
        with transaction.atomic(), sem_isolamento():
            nomes = self.pacientes()
            self.agendamentos(nomes)
            self.financeiro()
            self.rechamadas()
            self.profissionais()
            self.auditoria()
            r = self.resultado
            registrar(
                RegistroAuditoria.Acao.ALTERAR,
                clinica=self.clinica,
                descricao=(
                    f"Dados anonimizados: {r.pacientes} pacientes, {r.agendamentos} agendamentos, "
                    f"{r.rechamadas} rechamadas, {r.profissionais} profissionais"
                ),
            )
        return self.resultado


def anonimizar_clinica(nome_clinica, hoje=None):
    with sem_isolamento():
        clinica = Clinica.objects.filter(nome=nome_clinica).first()
    if clinica is None:
        raise ClinicaNaoEncontrada(f"Clínica “{nome_clinica}” não encontrada.")
    return _Anonimizador(clinica, hoje or timezone.localdate()).executar()
