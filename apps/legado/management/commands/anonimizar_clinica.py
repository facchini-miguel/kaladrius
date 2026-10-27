from django.core.management.base import BaseCommand, CommandError

from apps.legado.anonimizacao import ClinicaNaoEncontrada, anonimizar_clinica


class Command(BaseCommand):
    help = (
        "Replaces the personal data of a clinic (patients, appointment and recall "
        "descriptions, practitioner names) with fake values, keeping the structure, so real "
        "data can be used as test data. Cannot be undone."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinica", required=True, help="Name of the clinic.")
        parser.add_argument(
            "--confirmar", action="store_true", help="Required: the change cannot be undone."
        )

    def handle(self, *args, clinica, confirmar, **options):
        if not confirmar:
            raise CommandError("Nada foi alterado: rode de novo com --confirmar.")
        try:
            r = anonimizar_clinica(clinica)
        except ClinicaNaoEncontrada as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(self.style.SUCCESS(f"Dados da clínica “{clinica}” anonimizados:"))
        self.stdout.write(f"  Pacientes: {r.pacientes}")
        self.stdout.write(f"  Agendamentos: {r.agendamentos}")
        self.stdout.write(f"  Rechamadas: {r.rechamadas}")
        self.stdout.write(f"  Profissionais: {r.profissionais}")
        self.stdout.write(
            f"  Registros de auditoria com os dados originais apagados: {r.registros_apagados}"
        )
