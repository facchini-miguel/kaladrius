import datetime

from axes.models import AccessAttempt
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria

# Failed logins hold the username typed (personal data, sometimes a mistyped password):
# kept only long enough to investigate an attack (decision 045).
RETENCAO_LOGIN_FALHOU = datetime.timedelta(days=30)


class Command(BaseCommand):
    help = (
        "Deletes failed login records older than 30 days (audit log and django-axes). "
        "Run daily by deploy/servidor/backup.sh."
    )

    def handle(self, *args, **options):
        limite = timezone.now() - RETENCAO_LOGIN_FALHOU
        auditoria, _ = RegistroAuditoria.objects.filter(
            acao=RegistroAuditoria.Acao.LOGIN_FALHOU, momento__lt=limite
        ).delete()
        tentativas, _ = AccessAttempt.objects.filter(attempt_time__lt=limite).delete()
        self.stdout.write(
            f"Tentativas de entrada recusadas apagadas: {auditoria} da auditoria, "
            f"{tentativas} do bloqueio de senhas."
        )
