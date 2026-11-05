import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.isolation import without_isolation
from apps.core.models import Clinic
from apps.schedule.simulation import (
    simulate_appointments,
    simulate_commissions,
    simulate_estimates,
    simulate_finance,
    simulate_recalls,
)


class Command(BaseCommand):
    help = (
        "Adds FAKE appointments (from 2 weeks ago to 4 weeks ahead, with patients), "
        "recalls (from 30 days ago to 60 days ahead) and receivables (last 90 days) to a "
        "test clinic, so its screens have current activity. Never use it on a real clinic."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic", dest="clinic", required=True, help="Name of the test clinic."
        )
        parser.add_argument(
            "--recalls", dest="rechamadas", type=int, default=80, help="How many recalls."
        )
        parser.add_argument(
            "--no-schedule",
            dest="sem_agenda",
            action="store_true",
            help="Only recalls, no appointments.",
        )
        parser.add_argument(
            "--entries",
            dest="lancamentos",
            type=int,
            default=60,
            help="Fake receivables of the last 90 days, plus fake bills (0 for none).",
        )
        parser.add_argument(
            "--estimates",
            dest="orcamentos",
            type=int,
            default=20,
            help="Fake estimates of the last 60 days (0 for none).",
        )
        parser.add_argument(
            "--confirm",
            dest="confirmar",
            action="store_true",
            help="Required: fake data is mixed with the clinic's data.",
        )

    def handle(
        self, *args, clinic, rechamadas, sem_agenda, lancamentos, orcamentos, confirmar, **options
    ):
        if not confirmar:
            raise CommandError(
                "Nada foi criado: rode de novo com --confirm (só em clínicas de teste)."
            )
        sorteio = random.Random()  # noqa: S311 (fake data, not security)
        with transaction.atomic(), without_isolation():
            alvo = Clinic.objects.filter(name=clinic).first()
            if alvo is None:
                raise CommandError(f"Clínica “{clinic}” não encontrada.")
            agendamentos = 0 if sem_agenda else simulate_appointments(alvo, sorteio)
            criadas = simulate_recalls(alvo, sorteio, quantity=rechamadas)
            criados = simulate_estimates(alvo, sorteio, quantity=orcamentos) if orcamentos else 0
            receber, pagar = (
                simulate_finance(alvo, sorteio, quantity=lancamentos) if lancamentos else (0, 0)
            )
            comissoes = simulate_commissions(alvo, sorteio)
        self.stdout.write(self.style.SUCCESS(f"Movimento simulado na clínica “{clinic}”:"))
        self.stdout.write(f"  Agendamentos fictícios: {agendamentos}")
        self.stdout.write(f"  Rechamadas fictícias: {criadas}")
        self.stdout.write(f"  Lançamentos a receber fictícios: {receber}")
        self.stdout.write(f"  Despesas fictícias: {pagar}")
        self.stdout.write(f"  Orçamentos fictícios: {criados}")
        self.stdout.write(f"  Comissões lançadas (até o fim do mês passado): {comissoes}")
