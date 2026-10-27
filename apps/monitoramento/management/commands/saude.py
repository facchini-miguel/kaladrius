import datetime

from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from apps.core.models import Backup
from apps.monitoramento import saude


class Command(BaseCommand):
    help = (
        "Prints the last 24 hours of server health (from the samples of "
        "deploy/servidor/saude.sh) and the last backup. Used by saude.sh's report."
    )

    def handle(self, *args, **options):
        lista = saude.amostras(desde=timezone.now() - datetime.timedelta(hours=24))
        resumo = saude.resumo(lista)
        if resumo is None:
            self.stdout.write("Sem amostras nas últimas 24 horas: a coleta está funcionando?")
        else:
            ultima = lista[-1]
            self.stdout.write(
                f"Amostras: {resumo['amostras']} (a última às {ultima['momento']:%H:%M} UTC)"
            )
            self.stdout.write(
                f"Processador: média {resumo['cpu_media']:.1f}%, pico {resumo['cpu_maxima']:.1f}%"
            )
            self.stdout.write(
                f"Memória: pico {resumo['memoria_maxima']:.0f}% em uso; "
                f"swap: pico {resumo['swap_maximo']:.0f}%"
            )
            self.stdout.write(f"Disco: {resumo['disco']:.0f}% em uso")
            self.stdout.write(
                f"Rede: {filesizeformat(resumo['recebido'])} recebidos, "
                f"{filesizeformat(resumo['enviado'])} enviados"
            )
            alertas = [
                f"{chave}: {nivel}"
                for chave, nivel in saude.niveis(ultima).items()
                if nivel != "ok"
            ]
            if saude.parada(ultima):
                alertas.append("coleta parada")
            self.stdout.write("Alertas: " + (", ".join(alertas) if alertas else "nenhum"))
        backup = Backup.objects.first()
        if backup is None:
            self.stdout.write("Último backup: nenhum registrado")
        else:
            horas = (timezone.now() - backup.momento).total_seconds() / 3600
            self.stdout.write(
                f"Último backup: {backup.arquivo} ({filesizeformat(backup.tamanho)}), "
                f"há {horas:.0f} h"
            )
