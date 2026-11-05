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
            dest="confirmar",
            action="store_true",
            help="Required: the change cannot be undone.",
        )

    def handle(self, *args, clinic, confirmar, **options):
        if not confirmar:
            raise CommandError("Nada foi alterado: rode de novo com --confirm.")
        try:
            r = anonymize_clinic(clinic)
        except ClinicNotFound as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Dados da clínica “{clinic}” anonimizados:"))
        self.stdout.write(f"  Pacientes: {r.patients}")
        self.stdout.write(f"  Agendamentos: {r.appointments}")
        self.stdout.write(f"  Rechamadas: {r.recalls}")
        self.stdout.write(f"  Profissionais: {r.practitioners}")
        self.stdout.write(
            f"  Registros de auditoria com os dados originais apagados: {r.registros_apagados}"
        )
