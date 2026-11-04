"""Decision 154: from #24 (decision 145) until this fix, the app ran under the label "account"
(its folder's new name), so Django created empty tables account_duasetapas and
account_codigorecuperacao and used them instead of conta_*, where everything already was. The
label is "conta" again; what was saved in the account_* tables meanwhile (two-step verification
set up again, recovery codes) is copied here, for users who have nothing in conta_*.

The account_* tables, their row in django_migrations and their content types stay for now: an
automatic rollback to the version before this one still uses them. A later migration deletes them.
"""

from django.db import migrations


def copiar(apps, schema_editor):
    conexao = schema_editor.connection
    with conexao.cursor() as cursor:
        tabelas = conexao.introspection.table_names(cursor)
        if "account_duasetapas" in tabelas:
            cursor.execute(
                "INSERT INTO conta_duasetapas (usuario_id, segredo, ativa, ativada_em, ultimo_passo) "
                "SELECT a.usuario_id, a.segredo, a.ativa, a.ativada_em, a.ultimo_passo "
                "FROM account_duasetapas a WHERE NOT EXISTS "
                "(SELECT 1 FROM conta_duasetapas c WHERE c.usuario_id = a.usuario_id)"
            )
        if "account_codigorecuperacao" in tabelas:
            cursor.execute(
                "INSERT INTO conta_codigorecuperacao (usuario_id, resumo, usado_em) "
                "SELECT a.usuario_id, a.resumo, a.usado_em FROM account_codigorecuperacao a "
                "WHERE NOT EXISTS "
                "(SELECT 1 FROM conta_codigorecuperacao c WHERE c.usuario_id = a.usuario_id)"
            )


class Migration(migrations.Migration):
    dependencies = [("conta", "0001_initial")]

    operations = [migrations.RunPython(copiar, migrations.RunPython.noop)]
