"""The models' names in English (decision 157). The tables keep their names (db_table), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations


class Migration(migrations.Migration):
    # After every migration before this one in the project: the old migrations name these models
    # the old way, and a rename ordered before them would leave them pointing nowhere.
    dependencies = [
        ("agenda", "0005_ordem_alfabetica"),
        ("auditoria", "0001_initial"),
        ("conta", "0002_back_from_account_tables"),
        ("convenios", "0003_seguros_de_cada_pais"),
        ("core", "0018_numeracao_dentaria"),
        ("financeiro", "0016_formas_de_cada_pais"),
        ("orcamentos", "0003_codigo_do_procedimento"),
        ("pacientes", "0007_documento_do_pais"),
        ("pessoal", "0003_documento_do_pais"),
        ("profissionais", "0003_ordem_alfabetica"),
        ("prontuario", "0003_pedido_exames_anexo"),
        ("rechamadas", "0002_english_model_names"),
        ("referencias", "0005_english_model_names"),
    ]

    operations = [
        migrations.AlterModelTable(name="ItemOrcamento", table="orcamentos_itemorcamento"),
        migrations.AlterModelTable(name="Orcamento", table="orcamentos_orcamento"),
        migrations.AlterModelTable(name="Procedimento", table="orcamentos_procedimento"),
        migrations.RenameModel(old_name="ItemOrcamento", new_name="EstimateItem"),
        migrations.RenameModel(old_name="Orcamento", new_name="Estimate"),
        migrations.RenameModel(old_name="Procedimento", new_name="Procedure"),
    ]
