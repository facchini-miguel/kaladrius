"""The apps' labels before and after the English names (decisions 193 and 194).

A label names an app in two of the database's tables: `django_migrations` (which migrations ran)
and `django_content_type` (which permissions and admin log entries point to, by id). The tables'
own names do not depend on it: every model pins its `db_table` (decision 179).

`sync_labels` renames those rows to the labels the running code uses, in either direction, before
`migrate` reads them (apps/core/management/commands/migrate.py): a database of the version before
or after the label change, a restored backup or the demo's base all migrate as usual, and the
automatic rollback to the version before works on a database already renamed.
"""

from django.apps import apps
from django.db import connections, transaction

# Portuguese label -> English label (the app's folder).
LABELS = {
    "agenda": "schedule",
    "ajuda": "help",
    "auditoria": "audit",
    "conta": "account",
    "convenios": "health_plans",
    "equipe": "team",
    "financeiro": "finance",
    "legado": "legacy",
    "monitoramento": "monitoring",
    "novidades": "whats_new",
    "odontologia": "dentistry",
    "orcamentos": "estimates",
    "pacientes": "patients",
    "pessoal": "staff",
    "profissionais": "practitioners",
    "prontuario": "medical_records",
    "rechamadas": "recalls",
    "referencias": "reference_data",
}


def label_pairs():
    """(label in the database to rename, label of the running code) for each app."""
    for portuguese, english in LABELS.items():
        if portuguese in apps.app_configs:
            yield english, portuguese
        elif english in apps.app_configs:
            yield portuguese, english


def sync_labels(using="default"):
    """Rename the other spelling's rows to the running code's labels. Returns what changed:
    [(old label, new label, migrations renamed, content types renamed or merged)]."""
    connection = connections[using]
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
    if "django_migrations" not in tables:
        return []  # a new database: migrate creates everything with the code's labels
    changed = []
    with transaction.atomic(using=using), connection.cursor() as cursor:
        for old, new in label_pairs():
            migrations = _rename_migrations(cursor, old, new)
            content_types = (
                _rename_content_types(cursor, connection, tables, old, new)
                if "django_content_type" in tables
                else 0
            )
            if migrations or content_types:
                changed.append((old, new, migrations, content_types))
    return changed


def _rename_migrations(cursor, old, new):
    # A migration recorded under both labels keeps the code's row.
    cursor.execute(
        "DELETE FROM django_migrations m WHERE m.app = %s AND EXISTS ("
        "SELECT 1 FROM django_migrations n WHERE n.app = %s AND n.name = m.name)",
        [old, new],
    )
    cursor.execute("UPDATE django_migrations SET app = %s WHERE app = %s", [new, old])
    return cursor.rowcount


def _rename_content_types(cursor, connection, tables, old, new):
    cursor.execute(
        "SELECT o.id, n.id FROM django_content_type o LEFT JOIN django_content_type n "
        "ON n.app_label = %s AND n.model = o.model WHERE o.app_label = %s",
        [new, old],
    )
    pairs = cursor.fetchall()
    for old_id, new_id in pairs:
        if new_id is None:
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE id = %s", [new, old_id]
            )
        else:
            _merge_content_type(cursor, connection, tables, old_id, new_id)
    return len(pairs)


def _merge_content_type(cursor, connection, tables, old_id, new_id):
    """Both spellings have the model (one created while the other was in the database): the
    code's row stays, and what pointed to the other moves to it."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    if "auth_permission" in tables:
        cursor.execute(
            "SELECT o.id, n.id FROM auth_permission o LEFT JOIN auth_permission n "
            "ON n.content_type_id = %s AND n.codename = o.codename WHERE o.content_type_id = %s",
            [new_id, old_id],
        )
        for old_permission, new_permission in cursor.fetchall():
            if new_permission is None:
                cursor.execute(
                    "UPDATE auth_permission SET content_type_id = %s WHERE id = %s",
                    [new_id, old_permission],
                )
                continue
            for through in (
                Group.permissions.through,
                get_user_model().user_permissions.through,
            ):
                if through._meta.db_table not in tables:
                    continue
                # Names from the models, never from input: quoted, not parameters.
                table = connection.ops.quote_name(through._meta.db_table)
                # The group's or user's column, beside permission_id.
                owner = connection.ops.quote_name(
                    next(
                        f.column
                        for f in through._meta.fields
                        if f.is_relation and f.name != "permission"
                    )
                )
                cursor.execute(
                    f"UPDATE {table} t SET permission_id = %s WHERE t.permission_id = %s "  # noqa: S608
                    f"AND NOT EXISTS (SELECT 1 FROM {table} u WHERE u.permission_id = %s "
                    f"AND u.{owner} = t.{owner})",
                    [new_permission, old_permission, new_permission],
                )
                cursor.execute(
                    f"DELETE FROM {table} WHERE permission_id = %s",  # noqa: S608
                    [old_permission],
                )
            cursor.execute("DELETE FROM auth_permission WHERE id = %s", [old_permission])
    # Any other table pointing to content types (the admin log) follows the code's row.
    for table in sorted(tables):
        if table == "auth_permission":
            continue
        relations = connection.introspection.get_relations(cursor, table)
        for column, relation in relations.items():  # column: (target column, target table, …)
            if relation[1] == "django_content_type":
                quoted, field = connection.ops.quote_name(table), connection.ops.quote_name(column)
                cursor.execute(
                    f"UPDATE {quoted} SET {field} = %s WHERE {field} = %s",  # noqa: S608
                    [new_id, old_id],
                )
    cursor.execute("DELETE FROM django_content_type WHERE id = %s", [old_id])
