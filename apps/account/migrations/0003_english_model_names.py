"""The models' names in English (decision 157). The tables keep their names (db_table), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations


class Migration(migrations.Migration):
    # After every migration before this one in the project: the old migrations name these models
    # the old way, and a rename ordered before them would leave them pointing nowhere.
    dependencies = [
        ("schedule", "0005_ordem_alfabetica"),
        ("audit", "0001_initial"),
        ("account", "0002_back_from_account_tables"),
        ("health_plans", "0003_seguros_de_cada_pais"),
        ("core", "0018_numeracao_dentaria"),
        ("finance", "0016_formas_de_cada_pais"),
        ("estimates", "0003_codigo_do_procedimento"),
        ("patients", "0007_documento_do_pais"),
        ("staff", "0003_documento_do_pais"),
        ("practitioners", "0003_ordem_alfabetica"),
        ("medical_records", "0003_pedido_exames_anexo"),
        ("recalls", "0002_english_model_names"),
        ("reference_data", "0005_english_model_names"),
    ]

    operations = [
        migrations.AlterModelTable(name="CodigoRecuperacao", table="conta_codigorecuperacao"),
        migrations.AlterModelTable(name="DuasEtapas", table="conta_duasetapas"),
        migrations.RenameModel(old_name="CodigoRecuperacao", new_name="RecoveryCode"),
        migrations.RenameModel(old_name="DuasEtapas", new_name="TwoFactor"),
    ]
