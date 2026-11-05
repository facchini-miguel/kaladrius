import datetime

from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from apps.core.models import Backup
from apps.monitoring import health


class Command(BaseCommand):
    help = (
        "Prints the last 24 hours of server health (from the samples of "
        "deploy/server/health.sh) and the last backup. Used by health.sh's report."
    )

    def handle(self, *args, **options):
        results = health.amostras(desde=timezone.now() - datetime.timedelta(hours=24))
        summary = health.summary(results)
        if summary is None:
            self.stdout.write("Sem amostras nas últimas 24 horas: a coleta está funcionando?")
        else:
            ultima = results[-1]
            self.stdout.write(
                f"Amostras: {summary['amostras']} (a última às {ultima['momento']:%H:%M} UTC)"
            )
            self.stdout.write(
                f"Processador: média {summary['cpu_media']:.1f}%, pico {summary['cpu_maxima']:.1f}%"
            )
            self.stdout.write(
                f"Memória: pico {summary['memoria_maxima']:.0f}% em uso; "
                f"swap: pico {summary['swap_maximo']:.0f}%"
            )
            self.stdout.write(f"Disco: {summary['disco']:.0f}% em uso")
            self.stdout.write(
                f"Rede: {filesizeformat(summary['recebido'])} recebidos, "
                f"{filesizeformat(summary['enviado'])} enviados"
            )
            alertas = [
                f"{key}: {nivel}" for key, nivel in health.niveis(ultima).items() if nivel != "ok"
            ]
            if health.parada(ultima):
                alertas.append("coleta parada")
            self.stdout.write("Alertas: " + (", ".join(alertas) if alertas else "nenhum"))
        backup = Backup.objects.first()
        if backup is None:
            self.stdout.write("Último backup: nenhum registrado")
        else:
            horas = (timezone.now() - backup.timestamp).total_seconds() / 3600
            self.stdout.write(
                f"Último backup: {backup.file} ({filesizeformat(backup.size)}), há {horas:.0f} h"
            )
