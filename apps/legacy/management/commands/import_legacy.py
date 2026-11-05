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
            dest="codificacao",
            default="utf-8",
            help="Dump encoding (default: utf-8).",
        )

    def handle(self, *args, file, clinic, codificacao, **options):
        try:
            if file == "-":
                text = sys.stdin.buffer.read().decode(codificacao)
            else:
                text = Path(file).read_text(encoding=codificacao)
        except (OSError, UnicodeDecodeError) as error:
            raise CommandError(f"Não foi possível ler o arquivo: {error}") from error

        try:
            relatorio = import_dump(text, clinic)
        except (InvalidDump, ImportRefused) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"Importado na clínica “{relatorio.clinic.name}”:"))
        self.stdout.write(f"  Profissionais: {relatorio.practitioners}")
        self.stdout.write(f"  Tipos de atendimento novos: {relatorio.tipos_criados}")
        self.stdout.write(f"  Pacientes: {relatorio.patients}")
        self.stdout.write(f"  Agendamentos: {relatorio.appointments}")
        self.stdout.write(f"  Rechamadas: {relatorio.recalls}")
        if relatorio.avisos:
            self.stdout.write("Avisos:")
            for warning, total in sorted(relatorio.avisos.items()):
                self.stdout.write(f"  {total} × {warning}")
        self.stdout.write(
            "Nenhum usuário foi importado: crie a equipe em Cadastros › Equipe "
            "(e vincule o administrador da clínica pelo admin do Django)."
        )
