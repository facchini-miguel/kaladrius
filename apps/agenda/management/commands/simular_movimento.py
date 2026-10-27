import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agenda.simulacao import (
    simular_agendamentos,
    simular_financeiro,
    simular_orcamentos,
    simular_rechamadas,
)
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica


class Command(BaseCommand):
    help = (
        "Adds FAKE appointments (from 2 weeks ago to 4 weeks ahead, with patients), "
        "recalls (from 30 days ago to 60 days ahead) and receivables (last 90 days) to a "
        "test clinic, so its screens have current activity. Never use it on a real clinic."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinica", required=True, help="Name of the test clinic.")
        parser.add_argument("--rechamadas", type=int, default=80, help="How many recalls.")
        parser.add_argument(
            "--sem-agenda", action="store_true", help="Only recalls, no appointments."
        )
        parser.add_argument(
            "--lancamentos",
            type=int,
            default=60,
            help="Fake receivables of the last 90 days, plus fake bills (0 for none).",
        )
        parser.add_argument(
            "--orcamentos",
            type=int,
            default=20,
            help="Fake estimates of the last 60 days (0 for none).",
        )
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Required: fake data is mixed with the clinic's data.",
        )

    def handle(
        self, *args, clinica, rechamadas, sem_agenda, lancamentos, orcamentos, confirmar, **options
    ):
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
            criados = simular_orcamentos(alvo, sorteio, quantidade=orcamentos) if orcamentos else 0
            receber, pagar = (
                simular_financeiro(alvo, sorteio, quantidade=lancamentos) if lancamentos else (0, 0)
            )
        self.stdout.write(self.style.SUCCESS(f"Movimento simulado na clínica “{clinica}”:"))
        self.stdout.write(f"  Agendamentos fictícios: {agendamentos}")
        self.stdout.write(f"  Rechamadas fictícias: {criadas}")
        self.stdout.write(f"  Lançamentos a receber fictícios: {receber}")
        self.stdout.write(f"  Despesas fictícias: {pagar}")
        self.stdout.write(f"  Orçamentos fictícios: {criados}")
