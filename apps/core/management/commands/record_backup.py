from django.core.management.base import BaseCommand

from apps.core.models import Backup


class Command(BaseCommand):
    help = "Records a successful database backup (called by deploy/server/backup.sh)."

    def add_arguments(self, parser):
        parser.add_argument("file", metavar="file", help="Object name in the backup bucket.")
        parser.add_argument("size", metavar="size", type=int, help="Size in bytes.")

    def handle(self, *args, file, size, **options):
        Backup.objects.create(file=file, size=size)
        self.stdout.write(f"Backup registrado: {file}")
