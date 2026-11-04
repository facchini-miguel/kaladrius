from axes.models import AccessAttempt, AccessLog
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEntry
from apps.audit.record import registrar
from apps.core.isolation import sem_isolamento
from apps.core.models import Clinic, ClinicModule
from apps.estimates.models import Estimate, EstimateItem, Procedure
from apps.finance.models import (
    AccountGroup,
    BankTransaction,
    BookClosing,
    CashMovement,
    CashRegister,
    Category,
    Commission,
    CostCenter,
    Entry,
    FinancialAccount,
    Installment,
    Payment,
    Planning,
    StatementImport,
    Supplier,
)
from apps.health_plans.models import HealthPlan, MemberCard
from apps.medical_records.models import (
    Addendum,
    Attachment,
    Certificate,
    ExamRequest,
    Prescription,
    Visit,
)
from apps.patients.models import Patient, RelatedPerson
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule.models import Appointment, AppointmentType
from apps.staff.models import Employee, Payroll, Salary

from .seed_sample_data import CLINICAS

# Test data created before 0.26.0 (two clinics and a user in both): removed too.
CLINICAS_ANTIGAS = ["Clínica Bem Estar (teste)"]
USUARIOS_ANTIGOS = ["admin.bemestar", "recepcao.bemestar", "recepcao.multi"]


class Command(BaseCommand):
    help = (
        "Deletes the fake data created by seed_sample_data: the '(teste)' clinics with "
        "everything in them, the test users and their audit and login records. Real "
        "clinics and users are never touched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            dest="confirmar",
            action="store_true",
            help="Required: the deletion cannot be undone.",
        )

    def handle(self, *args, confirmar=False, **options):
        if not confirmar:
            raise CommandError("Nada foi apagado: rode de novo com --confirm.")
        nomes = [dados["nome"] for dados in CLINICAS] + CLINICAS_ANTIGAS
        usernames = [u[0] for dados in CLINICAS for u in dados["usuarios"]] + USUARIOS_ANTIGOS

        with transaction.atomic(), sem_isolamento():
            clinicas = list(Clinic.objects.filter(nome__in=nomes))
            # Only users that work solely in the test clinics, never a platform account.
            usuarios = list(
                get_user_model()
                .objects.filter(username__in=usernames, is_superuser=False, is_staff=False)
                .exclude(
                    vinculos__clinic__in=Clinic.objects.exclude(pk__in=[c.pk for c in clinicas])
                )
            )
            pacientes = Patient.objects.filter(clinic__in=clinicas).count()
            # Clinic data is protected against deleting the clinic, so it goes first. Groups of
            # the chart of accounts protect their parent group: unlink them first.
            AccountGroup.objects.filter(clinic__in=clinicas).update(pai=None)
            for modelo in (
                BankTransaction,
                StatementImport,
                EstimateItem,
                Estimate,
                Procedure,
                CashMovement,
                CashRegister,
                Payment,
                Commission,
                Installment,
                Addendum,
                Certificate,
                ExamRequest,
                Attachment,
                Prescription,
                Visit,
                Payroll,
                Salary,
                Employee,
                Entry,
                Supplier,
                Appointment,
                Recall,
                MemberCard,
                HealthPlan,
                RelatedPerson,
                Patient,
                Practitioner,
                AppointmentType,
                FinancialAccount,
                Category,
                Planning,
                AccountGroup,
                CostCenter,
                BookClosing,
                ClinicModule,
            ):
                modelo.objects.filter(clinic__in=clinicas).delete()
            # Collected now: delete() clears the instances' pk.
            ids_usuarios = [u.pk for u in usuarios]
            ids_clinicas = [c.pk for c in clinicas]
            for user in usuarios:
                user.delete()
            for clinic in clinicas:
                clinic.delete()
            # Their history, including the entries the deletion itself just wrote.
            AuditEntry.objects.filter(clinic_id__in=ids_clinicas).delete()
            AuditEntry.objects.filter(user_id__in=ids_usuarios).delete()
            AuditEntry.objects.filter(
                modelo__in=["Usuário", "Clínica"],
                objeto_id__in=[str(i) for i in ids_usuarios + ids_clinicas],
            ).delete()
            nomes_usuarios = [u.username for u in usuarios]
            AccessLog.objects.filter(username__in=nomes_usuarios).delete()
            AccessAttempt.objects.filter(username__in=nomes_usuarios).delete()
            registrar(
                AuditEntry.Acao.EXCLUIR,
                descricao=(
                    f"Dados de teste removidos: {len(clinicas)} clínicas, {pacientes} pacientes, "
                    f"{len(usuarios)} usuários"
                ),
            )

        self.stdout.write(self.style.SUCCESS("Dados de teste removidos."))
        self.stdout.write(f"Clínicas: {', '.join(c.nome for c in clinicas) or 'nenhuma'}")
        self.stdout.write(f"Pacientes fictícios: {pacientes}")
        self.stdout.write(f"Usuários: {', '.join(nomes_usuarios) or 'nenhum'}")
