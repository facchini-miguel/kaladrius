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
from apps.core.isolation import without_isolation
from apps.core.models import Clinic, Membership, Role
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient, RelatedPerson
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.reference_data.models import City, MaritalStatus
from apps.schedule.models import Appointment
from apps.schedule.simulation import simulate_appointments, simulate_recalls
from apps.staff.models import Employee, Salary

# Fake data only. Names, registrations and e-mails are invented.
CLINICS = [
    {
        "name": "Clínica Sorriso (teste)",
        "dados": {"phone": "(48) 3000-0001"},
        "usuarios": [
            ("admin.sorriso", "Beatriz", "Lima", Role.ADMIN),
            ("recepcao.sorriso", "Carla", "Mendes", Role.FRONT_DESK),
            ("financeiro.sorriso", "Diego", "Rocha", Role.FINANCE),
            ("dra.ana", "Ana", "Souza", Role.PRACTITIONER),
            ("dr.carlos", "Carlos", "Pereira", Role.PRACTITIONER),
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
            "--force", dest="force", action="store_true", help="Run even when DJANGO_DEBUG is off."
        )
        parser.add_argument(
            "--no-schedule",
            dest="no_schedule",
            action="store_true",
            help="Do not create fake appointments.",
        )
        parser.add_argument(
            "--patients",
            dest="patients",
            type=int,
            default=600,
            help="Fake patients per clinic (only for clinics without patients).",
        )

    def handle(self, *args, force=False, patients=600, no_schedule=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Dados de teste só podem ser criados com DJANGO_DEBUG=1 (use --force para ignorar)."
            )
        password = os.environ.get("DJANGO_SEED_PASSWORD")
        if not password:
            raise CommandError(
                "Defina DJANGO_SEED_PASSWORD no .env antes de criar os dados de teste."
            )

        created_count = []
        with transaction.atomic(), without_isolation():
            clinics = []
            for data in CLINICS:
                clinic, _ = Clinic.objects.get_or_create(name=data["name"], defaults=data["dados"])
                clinics.append(clinic)
                for username, name, sobrenome, role in data["usuarios"]:
                    user = self._user(username, name, sobrenome, password, created_count)
                    Membership.objects.get_or_create(
                        user=user, clinic=clinic, defaults={"role": role}
                    )
                for name, registration, color, username in data["profissionais"]:
                    user = get_user_model().objects.filter(username=username).first()
                    Practitioner.objects.get_or_create(
                        clinic=clinic,
                        name=name,
                        defaults={"registration": registration, "color": color, "user": user},
                    )

            patient_total = sum(self._patients(clinic, patients) for clinic in clinics)
            appointment_total = 0
            if not no_schedule:
                appointment_total = sum(self._appointments(clinic) for clinic in clinics)
            recall_total = sum(self._recalls(clinic) for clinic in clinics)
            for clinic in clinics:
                self._employees(clinic)
                self._related_people(clinic)

        self.stdout.write(self.style.SUCCESS("Dados de teste prontos."))
        self.stdout.write(f"Pacientes fictícios criados: {patient_total}")
        self.stdout.write(f"Agendamentos fictícios criados: {appointment_total}")
        self.stdout.write(f"Rechamadas fictícias criadas: {recall_total}")
        if created_count:
            self.stdout.write(
                f"Usuários criados (senha em DJANGO_SEED_PASSWORD): {', '.join(created_count)}"
            )
        else:
            self.stdout.write("Nenhum usuário novo: os dados de teste já existiam.")

    def _user(self, username, name, sobrenome, password, created_count):
        user, created = get_user_model().objects.get_or_create(
            username=username,
            defaults={
                "first_name": name,
                "last_name": sobrenome,
                "email": f"{username}@example.com",
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            created_count.append(username)
        return user

    def _patients(self, clinic, quantity):
        """Create fake patients for a clinic that has none. Returns how many were created."""
        if quantity <= 0 or Patient.objects.filter(clinic=clinic).exists():
            return 0
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(clinic.pk)  # same data every time for the same clinic
        cities = list(City.objects.filter(state__abbreviation="SC"))
        marital_statuses = list(MaritalStatus.objects.all())
        documents = set()
        new_ones = []
        for number in range(1, quantity + 1):
            is_company = number % 25 == 0  # about 4% companies
            if is_company:
                name = fake.company()
                document = fake_data.cnpj(fake)
            else:
                sex = fake.random_element(["F", "M"])
                name = fake.name_female() if sex == "F" else fake.name_male()
                document = fake_data.cpf(fake) if fake.boolean(85) else ""
            if document in documents:
                document = ""
            documents.add(document)
            city = fake.random_element(cities)
            mobile = f"489{fake.numerify('########')}"
            patient = Patient(
                clinic=clinic,
                kind=Patient.Kind.COMPANY if is_company else Patient.Kind.INDIVIDUAL,
                name=name,
                tax_id=document,
                mobile_phone=mobile,
                whatsapp=mobile,
                email=f"paciente{clinic.pk}.{number}@example.com",
                postal_code=f"88{fake.numerify('######')}",
                state_id=city.state_id,
                city=city,
                neighborhood=fake.neighborhood(),
                street=fake.street_name(),
                number=fake.building_number(),
                active=fake.boolean(95),
            )
            if is_company:
                patient.legal_name = f"{name} Ltda."
            else:
                patient.sex = sex
                patient.birth_date = fake.date_of_birth(minimum_age=0, maximum_age=90)
                patient.marital_status = fake.random_element(marital_statuses)
                patient.occupation = fake_data.occupation(fake)
            new_ones.append(patient)
        Patient.objects.bulk_create(new_ones, batch_size=500)
        self._member_cards(clinic, new_ones)
        return len(new_ones)

    def _member_cards(self, clinic, patients):
        """Two made-up health plans and a card for about a third of the patients."""
        rng = random.Random(clinic.pk + 2000)  # noqa: S311 (fake data, not security)
        health_plans = [
            HealthPlan.objects.create(clinic=clinic, name=name, registration=registration)
            for name, registration in (("Saúde Exemplo", "000001"), ("Plano Fictício", "000002"))
        ]
        today = timezone.localdate()
        MemberCard.objects.bulk_create(
            MemberCard(
                clinic=clinic,
                patient=patient,
                health_plan=rng.choice(health_plans),
                plan=rng.choice(["Enfermaria", "Apartamento", "Básico"]),
                number=f"{number:012d}",
                valid_until=today + datetime.timedelta(days=rng.randint(-60, 720)),
            )
            for number, patient in enumerate(patients, start=1)
            if rng.random() < 0.35
        )

    def _employees(self, clinic):
        """Two made-up employees with a salary, for the month's pay (decision 099)."""
        if Employee.objects.filter(clinic=clinic).exists():
            return
        hired_on = timezone.localdate().replace(day=1) - datetime.timedelta(days=400)
        for name, job_title, salary in (
            ("Lúcia Andrade (fictícia)", "Recepcionista", "2200.00"),
            ("Paulo Teixeira (fictício)", "Auxiliar de saúde bucal", "2500.00"),
        ):
            employee = Employee.objects.create(
                clinic=clinic, name=name, job_title=job_title, hired_on=hired_on
            )
            Salary.objects.create(
                clinic=clinic, employee=employee, amount=Decimal(salary), effective_from=hired_on
            )

    def _related_people(self, clinic):
        """A few family links between made-up patients and outside contacts (decision 101)."""
        if RelatedPerson.objects.filter(clinic=clinic).exists():
            return
        patients = list(
            Patient.objects.filter(clinic=clinic, kind=Patient.Kind.INDIVIDUAL).order_by("pk")[:12]
        )
        memberships = RelatedPerson.Relationship
        for i, membership in zip(
            range(0, 6, 2),
            (memberships.MOTHER, memberships.FATHER, memberships.SPOUSE),
            strict=False,
        ):
            if i + 1 < len(patients):
                RelatedPerson.objects.create(
                    clinic=clinic,
                    patient=patients[i],
                    other_patient=patients[i + 1],
                    relationship=membership,
                )
        for n, patient in enumerate(patients[6:9], start=1):
            RelatedPerson.objects.create(
                clinic=clinic,
                patient=patient,
                relationship=memberships.EMERGENCY,
                name=f"Contato fictício {n}",
                phone=f"4899000000{n}",
            )

    def _appointments(self, clinic):
        """Fill ~60% of the weekday slots from 2 weeks ago to 4 weeks ahead."""
        if Appointment.objects.filter(clinic=clinic).exists():
            return 0
        rng = random.Random(clinic.pk)  # noqa: S311 (fake data, not security)
        return simulate_appointments(clinic, rng)

    def _recalls(self, clinic):
        """About 80 recalls from 30 days ago to 60 days ahead; past ones mostly done."""
        if Recall.objects.filter(clinic=clinic).exists():
            return 0
        rng = random.Random(clinic.pk + 1000)  # noqa: S311 (fake data, not security)
        return simulate_recalls(clinic, rng)
