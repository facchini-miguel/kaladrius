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
        results = health.samples(since=timezone.now() - datetime.timedelta(hours=24))
        summary = health.summary(results)
        if summary is None:
            self.stdout.write("No samples in the last 24 hours: is the collection running?")
        else:
            latest = results[-1]
            self.stdout.write(
                f"Samples: {summary['samples']} (the last at {latest['time']:%H:%M} UTC)"
            )
            self.stdout.write(
                f"Processor: average {summary['cpu_avg']:.1f}%, peak {summary['cpu_max']:.1f}%"
            )
            self.stdout.write(
                f"Memory: peak {summary['memory_max']:.0f}% in use; "
                f"swap: peak {summary['swap_max']:.0f}%"
            )
            self.stdout.write(f"Disk: {summary['disk']:.0f}% in use")
            self.stdout.write(
                f"Network: {filesizeformat(summary['received'])} received, "
                f"{filesizeformat(summary['sent'])} sent"
            )
            alerts = [
                f"{key}: {level}" for key, level in health.levels(latest).items() if level != "ok"
            ]
            if health.stopped(latest):
                alerts.append("collection stopped")
            self.stdout.write("Alerts: " + (", ".join(alerts) if alerts else "none"))
        backup = Backup.objects.first()
        if backup is None:
            self.stdout.write("Last backup: none recorded")
        else:
            hours = (timezone.now() - backup.timestamp).total_seconds() / 3600
            self.stdout.write(
                f"Last backup: {backup.file} ({filesizeformat(backup.size)}), {hours:.0f} h ago"
            )
