"""Old migrations' data code, run on today's database (decision 180).

A migration that moves data uses the models of its time: tables and columns with the old
Portuguese names (decision 179 renamed them). Taking the whole database back to that migration
and forward again cost minutes per test. Instead, views with the old names over today's tables
let the migration's own function read and write the real rows, inside the test's transaction.
"""

import contextlib

from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.audit.old_names import OLD_FIELD_NAMES


def apps_at(*nodes):
    """The models as they were after these migrations."""
    return MigrationLoader(connection).project_state(list(nodes)).apps


def _column(historical_field, model):
    """Today's column of a field of the time (renamed or not), or None if it is gone."""
    new_name = OLD_FIELD_NAMES.get(model._meta.label, {}).get(
        historical_field.name, historical_field.name
    )
    try:
        return model._meta.get_field(new_name).column
    except Exception:  # a field removed since then
        return None


@contextlib.contextmanager
def tables_of_the_time(pairs):
    """[(model of the time, today's model)]: a view per pair, named as the old table."""
    quote = connection.ops.quote_name
    views = []
    with connection.cursor() as cursor:
        for old, new in pairs:
            columns = []
            for field in old._meta.concrete_fields:
                current = _column(field, new)
                origin = quote(current) if current else "NULL"
                columns.append(f"{origin} AS {quote(field.column)}")
            view, table = old._meta.db_table, new._meta.db_table
            cursor.execute(
                f"CREATE VIEW {quote(view)} AS SELECT {', '.join(columns)} FROM {quote(table)}"
            )
            pk = new._meta.pk.column
            cursor.execute(
                f"ALTER VIEW {quote(view)} ALTER COLUMN {quote(old._meta.pk.column)} "
                f"SET DEFAULT nextval(pg_get_serial_sequence(%s, %s))",
                [table, pk],
            )
            views.append(view)
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            for view in reversed(views):
                cursor.execute(f"DROP VIEW {quote(view)}")
