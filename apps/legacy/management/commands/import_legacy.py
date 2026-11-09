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
            raise CommandError(f"Could not read the file: {error}") from error

        try:
            report = import_dump(text, clinic)
        except (InvalidDump, ImportRefused) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"Imported into the clinic “{report.clinic.name}”:"))
        self.stdout.write(f"  Practitioners: {report.practitioners}")
        self.stdout.write(f"  New appointment types: {report.kinds_created}")
        self.stdout.write(f"  Patients: {report.patients}")
        self.stdout.write(f"  Appointments: {report.appointments}")
        self.stdout.write(f"  Recalls: {report.recalls}")
        if report.warnings:
            self.stdout.write("Warnings:")
            for warning, total in sorted(report.warnings.items()):
                self.stdout.write(f"  {total} × {warning}")
        self.stdout.write(
            "No user was imported: create the team in Records › Team "
            "(and link the clinic's administrator in the Django admin)."
        )
