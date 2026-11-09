from django.core.management.base import BaseCommand, CommandError

from apps.legacy.anonymization import ClinicNotFound, anonymize_clinic


class Command(BaseCommand):
    help = (
        "Replaces the personal data of a clinic (patients, appointment and recall "
        "descriptions, practitioner names) with fake values, keeping the structure, so real "
        "data can be used as test data. Cannot be undone."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinic", dest="clinic", required=True, help="Name of the clinic.")
        parser.add_argument(
            "--confirm",
            dest="confirm",
            action="store_true",
            help="Required: the change cannot be undone.",
        )

    def handle(self, *args, clinic, confirm, **options):
        if not confirm:
            raise CommandError("Nothing was changed: run it again with --confirm.")
        try:
            r = anonymize_clinic(clinic)
        except ClinicNotFound as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Data of the clinic “{clinic}” anonymized:"))
        self.stdout.write(f"  Patients: {r.patients}")
        self.stdout.write(f"  Appointments: {r.appointments}")
        self.stdout.write(f"  Recalls: {r.recalls}")
        self.stdout.write(f"  Practitioners: {r.practitioners}")
        self.stdout.write(f"  Audit entries with the original data deleted: {r.deleted_records}")
