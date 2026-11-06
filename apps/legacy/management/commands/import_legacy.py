import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.legacy.dump import InvalidDump
from apps.legacy.importer import ImportRefused, import_dump


class Command(BaseCommand):
    help = (
        "Imports patients, schedule and recalls from a dump of the legacy Odonto System "
        "into a new clinic. All or nothing. The dump has real patient data: keep it out of "
        "the repository and delete copies made on servers after the import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file", metavar="file", help="MySQL dump (.sql). Use - to read from stdin."
        )
        parser.add_argument(
            "--clinic", dest="clinic", required=True, help="Name of the clinic to create."
        )
        parser.add_argument(
            "--encoding",
            dest="encoding",
            default="utf-8",
            help="Dump encoding (default: utf-8).",
        )

    def handle(self, *args, file, clinic, encoding, **options):
        try:
            if file == "-":
                text = sys.stdin.buffer.read().decode(encoding)
            else:
                text = Path(file).read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError) as error:
            raise CommandError(f"Não foi possível ler o arquivo: {error}") from error

        try:
            report = import_dump(text, clinic)
        except (InvalidDump, ImportRefused) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"Importado na clínica “{report.clinic.name}”:"))
        self.stdout.write(f"  Profissionais: {report.practitioners}")
        self.stdout.write(f"  Tipos de atendimento novos: {report.kinds_created}")
        self.stdout.write(f"  Pacientes: {report.patients}")
        self.stdout.write(f"  Agendamentos: {report.appointments}")
        self.stdout.write(f"  Rechamadas: {report.recalls}")
        if report.warnings:
            self.stdout.write("Avisos:")
            for warning, total in sorted(report.warnings.items()):
                self.stdout.write(f"  {total} × {warning}")
        self.stdout.write(
            "Nenhum usuário foi importado: crie a equipe em Cadastros › Equipe "
            "(e vincule o administrador da clínica pelo admin do Django)."
        )
