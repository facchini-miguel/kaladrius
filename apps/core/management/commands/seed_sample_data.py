import datetime
import os
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core import fake_data
from apps.core.isolation import sem_isolamento
from apps.core.models import Clinic, Membership, Papel
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient, RelatedPerson
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.reference_data.models import City, MaritalStatus
from apps.schedule.models import Appointment
from apps.schedule.simulation import simular_agendamentos, simular_rechamadas
from apps.staff.models import Employee, Salary

# Fake data only. Names, registrations and e-mails are invented.
CLINICAS = [
    {
        "nome": "Clínica Sorriso (teste)",
        "dados": {"telefone": "(48) 3000-0001"},
        "usuarios": [
            ("admin.sorriso", "Beatriz", "Lima", Papel.ADMIN),
            ("recepcao.sorriso", "Carla", "Mendes", Papel.RECEPCAO),
            ("financeiro.sorriso", "Diego", "Rocha", Papel.FINANCEIRO),
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
            "--force", dest="forcar", action="store_true", help="Run even when DJANGO_DEBUG is off."
        )
        parser.add_argument(
            "--no-schedule",
            dest="sem_agenda",
            action="store_true",
            help="Do not create fake appointments.",
        )
        parser.add_argument(
            "--patients",
            dest="pacientes",
            type=int,
            default=600,
            help="Fake patients per clinic (only for clinics without patients).",
        )

    def handle(self, *args, forcar=False, pacientes=600, sem_agenda=False, **options):
        if not settings.DEBUG and not forcar:
            raise CommandError(
                "Dados de teste só podem ser criados com DJANGO_DEBUG=1 (use --force para ignorar)."
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
                clinic, _ = Clinic.objects.get_or_create(
                    nome=dados["nome"], defaults=dados["dados"]
                )
                clinicas.append(clinic)
                for username, nome, sobrenome, papel in dados["usuarios"]:
                    usuario = self._usuario(username, nome, sobrenome, senha, criados)
                    Membership.objects.get_or_create(
                        usuario=usuario, clinic=clinic, defaults={"papel": papel}
                    )
                for nome, registro, cor, username in dados["profissionais"]:
                    usuario = get_user_model().objects.filter(username=username).first()
                    Practitioner.objects.get_or_create(
                        clinic=clinic,
                        nome=nome,
                        defaults={"registro": registro, "cor": cor, "usuario": usuario},
                    )

            total_pacientes = sum(self._pacientes(clinic, pacientes) for clinic in clinicas)
            total_agendamentos = 0
            if not sem_agenda:
                total_agendamentos = sum(self._agendamentos(clinic) for clinic in clinicas)
            total_rechamadas = sum(self._rechamadas(clinic) for clinic in clinicas)
            for clinic in clinicas:
                self._funcionarios(clinic)
                self._relacionados(clinic)

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

    def _pacientes(self, clinic, quantidade):
        """Create fake patients for a clinic that has none. Returns how many were created."""
        if quantidade <= 0 or Patient.objects.filter(clinic=clinic).exists():
            return 0
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(clinic.pk)  # same data every time for the same clinic
        cidades = list(City.objects.filter(uf__sigla="SC"))
        estados_civis = list(MaritalStatus.objects.all())
        documentos = set()
        novos = []
        for numero in range(1, quantidade + 1):
            juridica = numero % 25 == 0  # about 4% companies
            if juridica:
                nome = fake.company()
                documento = fake_data.cnpj(fake)
            else:
                sexo = fake.random_element(["F", "M"])
                nome = fake.name_female() if sexo == "F" else fake.name_male()
                documento = fake_data.cpf(fake) if fake.boolean(85) else ""
            if documento in documentos:
                documento = ""
            documentos.add(documento)
            cidade = fake.random_element(cidades)
            celular = f"489{fake.numerify('########')}"
            paciente = Patient(
                clinic=clinic,
                tipo=Patient.Tipo.JURIDICA if juridica else Patient.Tipo.FISICA,
                nome=nome,
                cpf_cnpj=documento,
                telefone_celular=celular,
                whatsapp=celular,
                email=f"paciente{clinic.pk}.{numero}@example.com",
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
                paciente.profissao = fake_data.profissao(fake)
            novos.append(paciente)
        Patient.objects.bulk_create(novos, batch_size=500)
        self._carteirinhas(clinic, novos)
        return len(novos)

    def _carteirinhas(self, clinic, pacientes):
        """Two made-up health plans and a card for about a third of the patients."""
        sorteio = random.Random(clinic.pk + 2000)  # noqa: S311 (fake data, not security)
        convenios = [
            HealthPlan.objects.create(clinic=clinic, nome=nome, registro=registro)
            for nome, registro in (("Saúde Exemplo", "000001"), ("Plano Fictício", "000002"))
        ]
        hoje = timezone.localdate()
        MemberCard.objects.bulk_create(
            MemberCard(
                clinic=clinic,
                paciente=paciente,
                convenio=sorteio.choice(convenios),
                plano=sorteio.choice(["Enfermaria", "Apartamento", "Básico"]),
                numero=f"{numero:012d}",
                validade=hoje + datetime.timedelta(days=sorteio.randint(-60, 720)),
            )
            for numero, paciente in enumerate(pacientes, start=1)
            if sorteio.random() < 0.35
        )

    def _funcionarios(self, clinic):
        """Two made-up employees with a salary, for the month's pay (decision 099)."""
        if Employee.objects.filter(clinic=clinic).exists():
            return
        admissao = timezone.localdate().replace(day=1) - datetime.timedelta(days=400)
        for nome, cargo, salario in (
            ("Lúcia Andrade (fictícia)", "Recepcionista", "2200.00"),
            ("Paulo Teixeira (fictício)", "Auxiliar de saúde bucal", "2500.00"),
        ):
            funcionario = Employee.objects.create(
                clinic=clinic, nome=nome, cargo=cargo, admissao=admissao
            )
            Salary.objects.create(
                clinic=clinic, funcionario=funcionario, valor=Decimal(salario), desde=admissao
            )

    def _relacionados(self, clinic):
        """A few family links between made-up patients and outside contacts (decision 101)."""
        if RelatedPerson.objects.filter(clinic=clinic).exists():
            return
        pacientes = list(
            Patient.objects.filter(clinic=clinic, tipo=Patient.Tipo.FISICA).order_by("pk")[:12]
        )
        vinculos = RelatedPerson.Relationship
        for i, vinculo in zip(
            range(0, 6, 2), (vinculos.MAE, vinculos.PAI, vinculos.CONJUGE), strict=False
        ):
            if i + 1 < len(pacientes):
                RelatedPerson.objects.create(
                    clinic=clinic,
                    paciente=pacientes[i],
                    outro_paciente=pacientes[i + 1],
                    vinculo=vinculo,
                )
        for n, paciente in enumerate(pacientes[6:9], start=1):
            RelatedPerson.objects.create(
                clinic=clinic,
                paciente=paciente,
                vinculo=vinculos.EMERGENCIA,
                nome=f"Contato fictício {n}",
                telefone=f"4899000000{n}",
            )

    def _agendamentos(self, clinic):
        """Fill ~60% of the weekday slots from 2 weeks ago to 4 weeks ahead."""
        if Appointment.objects.filter(clinic=clinic).exists():
            return 0
        sorteio = random.Random(clinic.pk)  # noqa: S311 (fake data, not security)
        return simular_agendamentos(clinic, sorteio)

    def _rechamadas(self, clinic):
        """About 80 recalls from 30 days ago to 60 days ahead; past ones mostly done."""
        if Recall.objects.filter(clinic=clinic).exists():
            return 0
        sorteio = random.Random(clinic.pk + 1000)  # noqa: S311 (fake data, not security)
        return simular_rechamadas(clinic, sorteio)
