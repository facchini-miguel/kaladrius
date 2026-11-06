"""Decision 158: the leftovers of decision 154. From #24 until #35 the app ran under the label
"account", and Django created the tables account_duasetapas and account_codigorecuperacao, a row
for them in django_migrations and their content types. 0002 copied what they held to conta_*;
since then nothing uses them, and the previous version (the automatic rollback, decision 135) no
longer does either. Here they go: the tables (with copies of two-step secrets that no longer
serve), the migration rows and the content types (with their permissions).
"""

from django.db import migrations

TABELAS = ["account_codigorecuperacao", "account_duasetapas"]


def remover(apps, schema_editor):
    conexao = schema_editor.connection
    with conexao.cursor() as cursor:
        existentes = set(conexao.introspection.table_names(cursor))
        for tabela in TABELAS:
            if tabela in existentes:
                cursor.execute(f"DROP TABLE {conexao.ops.quote_name(tabela)}")
    # Since decision 194 "account" is this app's own label: its migration rows stay (migrate's
    # sync_labels already merged the leftovers into them), and only the leftovers' content types,
    # under the models' old names, go.
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.using(schema_editor.connection.alias).filter(
        app_label="account", model__in=["codigorecuperacao", "duasetapas"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0004_english_field_names_2"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(remover, migrations.RunPython.noop)]
