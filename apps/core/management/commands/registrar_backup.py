from django.core.management.base import BaseCommand

from apps.core.models import Backup


class Command(BaseCommand):
    help = "Records a successful database backup (called by deploy/servidor/backup.sh)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", help="Object name in the backup bucket.")
        parser.add_argument("tamanho", type=int, help="Size in bytes.")

    def handle(self, *args, arquivo, tamanho, **options):
        Backup.objects.create(arquivo=arquivo, tamanho=tamanho)
        self.stdout.write(f"Backup registrado: {arquivo}")
