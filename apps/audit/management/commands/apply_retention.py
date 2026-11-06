import datetime

from axes.models import AccessAttempt
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEntry

# Failed logins hold the username typed (personal data, sometimes a mistyped password):
# kept only long enough to investigate an attack (decision 045).
FAILED_LOGIN_RETENTION = datetime.timedelta(days=30)


class Command(BaseCommand):
    help = (
        "Deletes failed login records older than 30 days (audit log and django-axes). "
        "Run daily by deploy/server/backup.sh."
    )

    def handle(self, *args, **options):
        limit = timezone.now() - FAILED_LOGIN_RETENTION
        auditoria, _ = AuditEntry.objects.filter(
            action=AuditEntry.Action.LOGIN_FAILED, timestamp__lt=limit
        ).delete()
        attempts, _ = AccessAttempt.objects.filter(attempt_time__lt=limit).delete()
        self.stdout.write(
            f"Tentativas de entrada recusadas apagadas: {auditoria} da auditoria, "
            f"{attempts} do bloqueio de senhas."
        )
