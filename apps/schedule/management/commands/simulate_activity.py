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
            "--recalls", dest="recalls", type=int, default=80, help="How many recalls."
        )
        parser.add_argument(
            "--no-schedule",
            dest="no_schedule",
            action="store_true",
            help="Only recalls, no appointments.",
        )
        parser.add_argument(
            "--entries",
            dest="entries",
            type=int,
            default=60,
            help="Fake receivables of the last 90 days, plus fake bills (0 for none).",
        )
        parser.add_argument(
            "--estimates",
            dest="estimates",
            type=int,
            default=20,
            help="Fake estimates of the last 60 days (0 for none).",
        )
        parser.add_argument(
            "--confirm",
            dest="confirm",
            action="store_true",
            help="Required: fake data is mixed with the clinic's data.",
        )

    def handle(self, *args, clinic, recalls, no_schedule, entries, estimates, confirm, **options):
        if not confirm:
            raise CommandError(
                "Nada foi criado: rode de novo com --confirm (só em clínicas de teste)."
            )
        rng = random.Random()  # noqa: S311 (fake data, not security)
        with transaction.atomic(), without_isolation():
            target = Clinic.objects.filter(name=clinic).first()
            if target is None:
                raise CommandError(f"Clínica “{clinic}” não encontrada.")
            appointments = 0 if no_schedule else simulate_appointments(target, rng)
            created_recalls = simulate_recalls(target, rng, quantity=recalls)
            created_count = simulate_estimates(target, rng, quantity=estimates) if estimates else 0
            receivable_total, payable_total = (
                simulate_finance(target, rng, quantity=entries) if entries else (0, 0)
            )
            commissions = simulate_commissions(target, rng)
        self.stdout.write(self.style.SUCCESS(f"Movimento simulado na clínica “{clinic}”:"))
        self.stdout.write(f"  Agendamentos fictícios: {appointments}")
        self.stdout.write(f"  Rechamadas fictícias: {created_recalls}")
        self.stdout.write(f"  Lançamentos a receber fictícios: {receivable_total}")
        self.stdout.write(f"  Despesas fictícias: {payable_total}")
        self.stdout.write(f"  Orçamentos fictícios: {created_count}")
        self.stdout.write(f"  Comissões lançadas (até o fim do mês passado): {commissions}")
