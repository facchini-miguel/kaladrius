import datetime

from django.apps import apps
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.utils import timezone

# Dates about the person or the server, not the clinic's activity: they never move.
FIXED = {"pacientes.patient.birth_date", "core.backup.timestamp"}


def _is_fixed(modelo, field):
    return f"{modelo._meta.label_lower}.{field.name}" in FIXED


def date_fields():
    """(model, [date fields]) of every table of the project's apps."""
    for modelo in apps.get_models():
        if not modelo.__module__.startswith("apps.") or modelo._meta.proxy:
            continue
        fields = [
            field
            for field in modelo._meta.local_concrete_fields
            if isinstance(field, models.DateField) and not _is_fixed(modelo, field)
        ]
        if fields:
            yield modelo, fields


class Command(BaseCommand):
    help = (
        "Demo server only (DJANGO_DEMO=1, decision 086): moves every date of the "
        "clinic's activity (schedule, recalls, finance, estimates, medical records, audit) "
        "forward by the whole weeks since --since, so the restored demo looks current and "
        "each appointment stays on its weekday. Birth dates do not move."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since", dest="desde", required=True, help="Date the data refers to (YYYY-MM-DD)."
        )
        parser.add_argument("--confirm", dest="confirmar", action="store_true", help="Required.")

    def handle(self, *args, desde, confirmar, **options):
        if not settings.DEMO:
            raise CommandError("Só no servidor de demonstração (DJANGO_DEMO=1).")
        if not confirmar:
            raise CommandError("Nada foi alterado: rode de novo com --confirm.")
        try:
            start = datetime.date.fromisoformat(desde)
        except ValueError as error:
            raise CommandError(f"Data inválida: {desde}") from error
        days = (timezone.localdate() - start).days // 7 * 7
        if days <= 0:
            self.stdout.write("Menos de uma semana: nada a avançar.")
            return

        tables = list(date_fields())
        # Moving everything at once would briefly overlap one appointment with the next
        # week's, so the no-double-booking constraint is set aside during the update.
        exclusoes = [
            (modelo, restricao)
            for modelo, _campos in tables
            for restricao in modelo._meta.constraints
            if isinstance(restricao, ExclusionConstraint)
        ]
        rows = 0
        with connection.schema_editor() as editor:
            editor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for modelo, restricao in exclusoes:
                editor.remove_constraint(modelo, restricao)
            for modelo, fields in tables:
                atribuicoes = ", ".join(
                    f"{editor.quote_name(c.column)} = {editor.quote_name(c.column)} + "
                    + ("make_interval(days => %s)" if isinstance(c, models.DateTimeField) else "%s")
                    for c in fields
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        # Names come from the models, never from users; values are parameters.
                        f"UPDATE {editor.quote_name(modelo._meta.db_table)} SET {atribuicoes}",  # noqa: S608
                        [days] * len(fields),
                    )
                    rows += cursor.rowcount
            # Deferred foreign key checks queued by the updates must run first: PostgreSQL
            # refuses ALTER TABLE on a table with pending trigger events.
            editor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for modelo, restricao in exclusoes:
                editor.add_constraint(modelo, restricao)
        self.stdout.write(
            self.style.SUCCESS(
                f"Datas avançadas {days // 7} semana(s) ({days} dias): "
                f"{rows} registros em {len(tables)} tabelas."
            )
        )
