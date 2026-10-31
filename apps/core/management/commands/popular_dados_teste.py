import datetime
import os
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.agenda.models import Agendamento
from apps.agenda.simulacao import simular_agendamentos, simular_rechamadas
from apps.convenios.models import Carteirinha, Convenio
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica, Papel, Vinculo
from apps.core.validadores import somente_digitos
from apps.pacientes.models import Paciente, PessoaRelacionada
from apps.pessoal.models import Funcionario, Salario
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada
from apps.referencias.models import Cidade, EstadoCivil

# Fake data only. Names, registrations and e-mails are invented.
CLINICAS = [
    {
        "nome": "Clínica Sorriso (teste)",
        "dados": {"telefone": "(48) 3000-0001"},
        "usuarios": [
            ("admin.sorriso", "Beatriz", "Lima", Papel.ADMIN),
            ("recepcao.sorriso", "Carla", "Mendes", Papel.RECEPCAO),
            ("dra.ana", "Ana", "Souza", Papel.PROFISSIONAL),
            ("dr.carlos", "Carlos", "Pereira", Papel.PROFISSIONAL),
        ],
        "profissionais": [
            ("Dra. Ana Souza", "CRO-SC 10001", "#0d6efd", "dra.ana"),
            ("Dr. Bruno Alves", "CRO-SC 10002", "#198754", None),
            ("Dr. Carlos Pereira", "CRM-SC 20001", "#dc3545", "dr.carlos"),
            ("Júlia Rocha (fisioterapia)", "CREFITO-10 20002", "#fd7e14", None),
            ("Consultório 2", "", "#6f42c1", None),
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Creates fake test data (one clinic, users and practitioners). "
        "Development only: never run it in production."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcar", action="store_true", help="Run even when DJANGO_DEBUG is off."
        )
        parser.add_argument(
            "--sem-agenda",
            action="store_true",
            help="Do not create fake appointments.",
        )
        parser.add_argument(
            "--pacientes",
            type=int,
            default=600,
            help="Fake patients per clinic (only for clinics without patients).",
        )

    def handle(self, *args, forcar=False, pacientes=600, sem_agenda=False, **options):
        if not settings.DEBUG and not forcar:
            raise CommandError(
                "Dados de teste só podem ser criados com DJANGO_DEBUG=1 "
                "(use --forcar para ignorar)."
            )
        senha = os.environ.get("DJANGO_SEED_PASSWORD")
        if not senha:
            raise CommandError(
                "Defina DJANGO_SEED_PASSWORD no .env antes de criar os dados de teste."
            )

        criados = []
        with transaction.atomic(), sem_isolamento():
            clinicas = []
            for dados in CLINICAS:
                clinica, _ = Clinica.objects.get_or_create(
                    nome=dados["nome"], defaults=dados["dados"]
                )
                clinicas.append(clinica)
                for username, nome, sobrenome, papel in dados["usuarios"]:
                    usuario = self._usuario(username, nome, sobrenome, senha, criados)
                    Vinculo.objects.get_or_create(
                        usuario=usuario, clinica=clinica, defaults={"papel": papel}
                    )
                for nome, registro, cor, username in dados["profissionais"]:
                    usuario = get_user_model().objects.filter(username=username).first()
                    Profissional.objects.get_or_create(
                        clinica=clinica,
                        nome=nome,
                        defaults={"registro": registro, "cor": cor, "usuario": usuario},
                    )

            total_pacientes = sum(self._pacientes(clinica, pacientes) for clinica in clinicas)
            total_agendamentos = 0
            if not sem_agenda:
                total_agendamentos = sum(self._agendamentos(clinica) for clinica in clinicas)
            total_rechamadas = sum(self._rechamadas(clinica) for clinica in clinicas)
            for clinica in clinicas:
                self._funcionarios(clinica)
                self._relacionados(clinica)

        self.stdout.write(self.style.SUCCESS("Dados de teste prontos."))
        self.stdout.write(f"Pacientes fictícios criados: {total_pacientes}")
        self.stdout.write(f"Agendamentos fictícios criados: {total_agendamentos}")
        self.stdout.write(f"Rechamadas fictícias criadas: {total_rechamadas}")
        if criados:
            self.stdout.write(
                f"Usuários criados (senha em DJANGO_SEED_PASSWORD): {', '.join(criados)}"
            )
        else:
            self.stdout.write("Nenhum usuário novo: os dados de teste já existiam.")

    def _usuario(self, username, nome, sobrenome, senha, criados):
        usuario, criado = get_user_model().objects.get_or_create(
            username=username,
            defaults={
                "first_name": nome,
                "last_name": sobrenome,
                "email": f"{username}@example.com",
            },
        )
        if criado:
            usuario.set_password(senha)
            usuario.save(update_fields=["password"])
            criados.append(username)
        return usuario

    def _pacientes(self, clinica, quantidade):
        """Create fake patients for a clinic that has none. Returns how many were created."""
        if quantidade <= 0 or Paciente.objects.filter(clinica=clinica).exists():
            return 0
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(clinica.pk)  # same data every time for the same clinic
        cidades = list(Cidade.objects.filter(uf__sigla="SC"))
        estados_civis = list(EstadoCivil.objects.all())
        documentos = set()
        novos = []
        for numero in range(1, quantidade + 1):
            juridica = numero % 25 == 0  # about 4% companies
            if juridica:
                nome = fake.company()
                documento = somente_digitos(fake.cnpj())
            else:
                sexo = fake.random_element(["F", "M"])
                nome = fake.name_female() if sexo == "F" else fake.name_male()
                documento = somente_digitos(fake.cpf()) if fake.boolean(85) else ""
            if documento in documentos:
                documento = ""
            documentos.add(documento)
            cidade = fake.random_element(cidades)
            celular = f"489{fake.numerify('########')}"
            paciente = Paciente(
                clinica=clinica,
                tipo=Paciente.Tipo.JURIDICA if juridica else Paciente.Tipo.FISICA,
                nome=nome,
                cpf_cnpj=documento,
                telefone_celular=celular,
                whatsapp=celular,
                email=f"paciente{clinica.pk}.{numero}@example.com",
                cep=f"88{fake.numerify('######')}",
                uf_id=cidade.uf_id,
                cidade=cidade,
                bairro=fake.bairro(),
                logradouro=fake.street_name(),
                numero=fake.building_number(),
                ativo=fake.boolean(95),
            )
            if juridica:
                paciente.razao_social = f"{nome} Ltda."
            else:
                paciente.sexo = sexo
                paciente.data_nascimento = fake.date_of_birth(minimum_age=0, maximum_age=90)
                paciente.estado_civil = fake.random_element(estados_civis)
                paciente.profissao = fake.job()[:100]
            novos.append(paciente)
        Paciente.objects.bulk_create(novos, batch_size=500)
        self._carteirinhas(clinica, novos)
        return len(novos)

    def _carteirinhas(self, clinica, pacientes):
        """Two made-up health plans and a card for about a third of the patients."""
        sorteio = random.Random(clinica.pk + 2000)  # noqa: S311 (fake data, not security)
        convenios = [
            Convenio.objects.create(clinica=clinica, nome=nome, registro_ans=registro)
            for nome, registro in (("Saúde Exemplo", "000001"), ("Plano Fictício", "000002"))
        ]
        hoje = timezone.localdate()
        Carteirinha.objects.bulk_create(
            Carteirinha(
                clinica=clinica,
                paciente=paciente,
                convenio=sorteio.choice(convenios),
                plano=sorteio.choice(["Enfermaria", "Apartamento", "Básico"]),
                numero=f"{numero:012d}",
                validade=hoje + datetime.timedelta(days=sorteio.randint(-60, 720)),
            )
            for numero, paciente in enumerate(pacientes, start=1)
            if sorteio.random() < 0.35
        )

    def _funcionarios(self, clinica):
        """Two made-up employees with a salary, for the month's pay (decision 099)."""
        if Funcionario.objects.filter(clinica=clinica).exists():
            return
        admissao = timezone.localdate().replace(day=1) - datetime.timedelta(days=400)
        for nome, cargo, salario in (
            ("Lúcia Andrade (fictícia)", "Recepcionista", "2200.00"),
            ("Paulo Teixeira (fictício)", "Auxiliar de saúde bucal", "2500.00"),
        ):
            funcionario = Funcionario.objects.create(
                clinica=clinica, nome=nome, cargo=cargo, admissao=admissao
            )
            Salario.objects.create(
                clinica=clinica, funcionario=funcionario, valor=Decimal(salario), desde=admissao
            )

    def _relacionados(self, clinica):
        """A few family links between made-up patients and outside contacts (decision 101)."""
        if PessoaRelacionada.objects.filter(clinica=clinica).exists():
            return
        pacientes = list(
            Paciente.objects.filter(clinica=clinica, tipo=Paciente.Tipo.FISICA).order_by("pk")[:12]
        )
        vinculos = PessoaRelacionada.Vinculo
        for i, vinculo in zip(
            range(0, 6, 2), (vinculos.MAE, vinculos.PAI, vinculos.CONJUGE), strict=False
        ):
            if i + 1 < len(pacientes):
                PessoaRelacionada.objects.create(
                    clinica=clinica,
                    paciente=pacientes[i],
                    outro_paciente=pacientes[i + 1],
                    vinculo=vinculo,
                )
        for n, paciente in enumerate(pacientes[6:9], start=1):
            PessoaRelacionada.objects.create(
                clinica=clinica,
                paciente=paciente,
                vinculo=vinculos.EMERGENCIA,
                nome=f"Contato fictício {n}",
                telefone=f"5499000000{n}",
            )

    def _agendamentos(self, clinica):
        """Fill ~60% of the weekday slots from 2 weeks ago to 4 weeks ahead."""
        if Agendamento.objects.filter(clinica=clinica).exists():
            return 0
        sorteio = random.Random(clinica.pk)  # noqa: S311 (fake data, not security)
        return simular_agendamentos(clinica, sorteio)

    def _rechamadas(self, clinica):
        """About 80 recalls from 30 days ago to 60 days ahead; past ones mostly done."""
        if Rechamada.objects.filter(clinica=clinica).exists():
            return 0
        sorteio = random.Random(clinica.pk + 1000)  # noqa: S311 (fake data, not security)
        return simular_rechamadas(clinica, sorteio)
