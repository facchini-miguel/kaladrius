import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agenda.simulacao import simular_agendamentos, simular_rechamadas
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica


class Command(BaseCommand):
    help = (
        "Adds FAKE appointments (from 2 weeks ago to 4 weeks ahead, with patients) and "
        "recalls (from 30 days ago to 60 days ahead) to a test clinic, so its schedule "
        "and recall screens have current activity. Never use it on a real clinic."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinica", required=True, help="Name of the test clinic.")
        parser.add_argument("--rechamadas", type=int, default=80, help="How many recalls.")
        parser.add_argument(
            "--sem-agenda", action="store_true", help="Only recalls, no appointments."
        )
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Required: fake data is mixed with the clinic's data.",
        )

    def handle(self, *args, clinica, rechamadas, sem_agenda, confirmar, **options):
        if not confirmar:
            raise CommandError(
                "Nada foi criado: rode de novo com --confirmar (só em clínicas de teste)."
            )
        sorteio = random.Random()  # noqa: S311 (fake data, not security)
        with transaction.atomic(), sem_isolamento():
            alvo = Clinica.objects.filter(nome=clinica).first()
            if alvo is None:
                raise CommandError(f"Clínica “{clinica}” não encontrada.")
            agendamentos = 0 if sem_agenda else simular_agendamentos(alvo, sorteio)
            criadas = simular_rechamadas(alvo, sorteio, quantidade=rechamadas)
        self.stdout.write(self.style.SUCCESS(f"Movimento simulado na clínica “{clinica}”:"))
        self.stdout.write(f"  Agendamentos fictícios: {agendamentos}")
        self.stdout.write(f"  Rechamadas fictícias: {criadas}")
