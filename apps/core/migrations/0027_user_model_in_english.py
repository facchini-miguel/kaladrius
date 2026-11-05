"""The user model is User (decision 179). The migrations that created it now name it so, with
the table it had (core_usuario, renamed by 0025); a database created before this keeps two
traces of the old name, which this migration renames: the user's column in the tables of
groups and permissions (usuario_id), and its content type and permissions (core.usuario,
view_usuario...). A database created after it has neither. Going back changes nothing."""

import importlib

from django.db import migrations

_names = importlib.import_module("apps.core.migrations.0026_generated_names_in_english")


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    with connection.cursor() as cursor:
        for table in ("core_user_groups", "core_user_user_permissions"):
            columns = [c.name for c in connection.introspection.get_table_description(cursor, table)]
            if "usuario_id" in columns:
                cursor.execute(
                    f"ALTER TABLE {quote(table)} RENAME COLUMN {quote('usuario_id')} TO {quote('user_id')}"
                )
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    old = ContentType.objects.filter(app_label="core", model="usuario").first()
    if old is not None and not ContentType.objects.filter(app_label="core", model="user").exists():
        old.model = "user"
        old.save(update_fields=["model"])
        for permission in Permission.objects.filter(content_type=old, codename__endswith="_usuario"):
            permission.codename = permission.codename.removesuffix("_usuario") + "_user"
            permission.save(update_fields=["codename"])
    # The renamed column's constraints and indexes get today's names too, and so does the
    # admin log's key to the user (django_admin_log_user_id_..._fk_core_usuario_id).
    _names.rename(apps, schema_editor)
    _names.rename_table(schema_editor, apps.get_model("admin", "LogEntry"), _names._named(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_generated_names_in_english"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop, elidable=False)]
