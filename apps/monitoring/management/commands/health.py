import datetime

from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from apps.core.models import Backup
from apps.monitoring import health

# The report keeps its Portuguese words (it was written with the old internal names).
LABELS = {"cpu": "cpu", "memory": "memoria", "swap": "swap", "disk": "disco"}


class Command(BaseCommand):
    help = (
        "Prints the last 24 hours of server health (from the samples of "
        "deploy/server/health.sh) and the last backup. Used by health.sh's report."
    )

    def handle(self, *args, **options):
        results = health.samples(desde=timezone.now() - datetime.timedelta(hours=24))
        summary = health.summary(results)
        if summary is None:
            self.stdout.write("Sem amostras nas últimas 24 horas: a coleta está funcionando?")
        else:
            latest = results[-1]
            self.stdout.write(
                f"Amostras: {summary['samples']} (a última às {latest['time']:%H:%M} UTC)"
            )
            self.stdout.write(
                f"Processador: média {summary['cpu_avg']:.1f}%, pico {summary['cpu_max']:.1f}%"
            )
            self.stdout.write(
                f"Memória: pico {summary['memory_max']:.0f}% em uso; "
                f"swap: pico {summary['swap_max']:.0f}%"
            )
            self.stdout.write(f"Disco: {summary['disk']:.0f}% em uso")
            self.stdout.write(
                f"Rede: {filesizeformat(summary['received'])} recebidos, "
                f"{filesizeformat(summary['sent'])} enviados"
            )
            alerts = [
                f"{LABELS[key]}: {level}"
                for key, level in health.levels(latest).items()
                if level != "ok"
            ]
            if health.stopped(latest):
                alerts.append("coleta parada")
            self.stdout.write("Alertas: " + (", ".join(alerts) if alerts else "nenhum"))
        backup = Backup.objects.first()
        if backup is None:
            self.stdout.write("Último backup: nenhum registrado")
        else:
            horas = (timezone.now() - backup.timestamp).total_seconds() / 3600
            self.stdout.write(
                f"Último backup: {backup.file} ({filesizeformat(backup.size)}), há {horas:.0f} h"
            )
