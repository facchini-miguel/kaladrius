from axes.models import AccessAttempt, AccessLog
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit import events
from apps.audit.models import AuditEntry
from apps.audit.record import log_event, model_label
from apps.core.isolation import without_isolation
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

from .seed_sample_data import CLINICS

# Test data created before 0.26.0 (two clinics and a user in both): removed too.
OLD_CLINICS = ["Clínica Bem Estar (teste)"]
OLD_USERS = ["admin.bemestar", "recepcao.bemestar", "recepcao.multi"]


class Command(BaseCommand):
    help = (
        "Deletes the fake data created by seed_sample_data: the '(teste)' clinics with "
        "everything in them, the test users and their audit and login records. Real "
        "clinics and users are never touched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            dest="confirm",
            action="store_true",
            help="Required: the deletion cannot be undone.",
        )

    def handle(self, *args, confirm=False, **options):
        if not confirm:
            raise CommandError("Nothing was deleted: run it again with --confirm.")
        names = [data["name"] for data in CLINICS] + OLD_CLINICS
        usernames = [u[0] for data in CLINICS for u in data["users"]] + OLD_USERS

        with transaction.atomic(), without_isolation():
            clinics = list(Clinic.objects.filter(name__in=names))
            # Only users that work solely in the test clinics, never a platform account.
            users = list(
                get_user_model()
                .objects.filter(username__in=usernames, is_superuser=False, is_staff=False)
                .exclude(
                    memberships__clinic__in=Clinic.objects.exclude(pk__in=[c.pk for c in clinics])
                )
            )
            patients = Patient.objects.filter(clinic__in=clinics).count()
            # Clinic data is protected against deleting the clinic, so it goes first. Groups of
            # the chart of accounts protect their parent group: unlink them first.
            AccountGroup.objects.filter(clinic__in=clinics).update(parent=None)
            for model in (
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
                model.objects.filter(clinic__in=clinics).delete()
            # Collected now: delete() clears the instances' pk.
            user_ids = [u.pk for u in users]
            clinic_ids = [c.pk for c in clinics]
            for user in users:
                user.delete()
            for clinic in clinics:
                clinic.delete()
            # Their history, including the entries the deletion itself just wrote.
            AuditEntry.objects.filter(clinic_id__in=clinic_ids).delete()
            AuditEntry.objects.filter(user_id__in=user_ids).delete()
            AuditEntry.objects.filter(
                model_name__in=[model_label(get_user_model()), model_label(Clinic)],
                object_id__in=[str(i) for i in user_ids + clinic_ids],
            ).delete()
            deleted_usernames = [u.username for u in users]
            AccessLog.objects.filter(username__in=deleted_usernames).delete()
            AccessAttempt.objects.filter(username__in=deleted_usernames).delete()
            log_event(
                AuditEntry.Action.DELETE,
                event=events.SAMPLE_DATA_REMOVED,
                values={"clinics": len(clinics), "patients": patients, "users": len(users)},
            )

        self.stdout.write(self.style.SUCCESS("Sample data removed."))
        self.stdout.write(f"Clinics: {', '.join(c.name for c in clinics) or 'none'}")
        self.stdout.write(f"Fake patients: {patients}")
        self.stdout.write(f"Users: {', '.join(deleted_usernames) or 'none'}")
