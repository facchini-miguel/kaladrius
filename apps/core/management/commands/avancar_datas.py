import datetime

from django.apps import apps
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.utils import timezone

# Dates about the person or the server, not the clinic's activity: they never move.
FIXAS = {"pacientes.paciente.data_nascimento", "core.backup.momento"}


def _fixa(modelo, campo):
    return f"{modelo._meta.label_lower}.{campo.name}" in FIXAS


def campos_de_data():
    """(model, [date fields]) of every table of the project's apps."""
    for modelo in apps.get_models():
        if not modelo.__module__.startswith("apps.") or modelo._meta.proxy:
            continue
        campos = [
            campo
            for campo in modelo._meta.local_concrete_fields
            if isinstance(campo, models.DateField) and not _fixa(modelo, campo)
        ]
        if campos:
            yield modelo, campos


class Command(BaseCommand):
    help = (
        "Demo server only (DJANGO_DEMONSTRACAO=1, decision 086): moves every date of the "
        "clinic's activity (schedule, recalls, finance, estimates, medical records, audit) "
        "forward by the whole weeks since --desde, so the restored demo looks current and "
        "each appointment stays on its weekday. Birth dates do not move."
    )

    def add_arguments(self, parser):
        parser.add_argument("--desde", required=True, help="Date the data refers to (YYYY-MM-DD).")
        parser.add_argument("--confirmar", action="store_true", help="Required.")

    def handle(self, *args, desde, confirmar, **options):
        if not settings.DEMONSTRACAO:
            raise CommandError("Só no servidor de demonstração (DJANGO_DEMONSTRACAO=1).")
        if not confirmar:
            raise CommandError("Nada foi alterado: rode de novo com --confirmar.")
        try:
            inicio = datetime.date.fromisoformat(desde)
        except ValueError as erro:
            raise CommandError(f"Data inválida: {desde}") from erro
        dias = (timezone.localdate() - inicio).days // 7 * 7
        if dias <= 0:
            self.stdout.write("Menos de uma semana: nada a avançar.")
            return

        tabelas = list(campos_de_data())
        # Moving everything at once would briefly overlap one appointment with the next
        # week's, so the no-double-booking constraint is set aside during the update.
        exclusoes = [
            (modelo, restricao)
            for modelo, _campos in tabelas
            for restricao in modelo._meta.constraints
            if isinstance(restricao, ExclusionConstraint)
        ]
        linhas = 0
        with connection.schema_editor() as editor:
            editor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for modelo, restricao in exclusoes:
                editor.remove_constraint(modelo, restricao)
            for modelo, campos in tabelas:
                atribuicoes = ", ".join(
                    f"{editor.quote_name(c.column)} = {editor.quote_name(c.column)} + "
                    + ("make_interval(days => %s)" if isinstance(c, models.DateTimeField) else "%s")
                    for c in campos
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        # Names come from the models, never from users; values are parameters.
                        f"UPDATE {editor.quote_name(modelo._meta.db_table)} SET {atribuicoes}",  # noqa: S608
                        [dias] * len(campos),
                    )
                    linhas += cursor.rowcount
            # Deferred foreign key checks queued by the updates must run first: PostgreSQL
            # refuses ALTER TABLE on a table with pending trigger events.
            editor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            for modelo, restricao in exclusoes:
                editor.add_constraint(modelo, restricao)
        self.stdout.write(
            self.style.SUCCESS(
                f"Datas avançadas {dias // 7} semana(s) ({dias} dias): "
                f"{linhas} registros em {len(tabelas)} tabelas."
            )
        )
