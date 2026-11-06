"""The models' names in English (decision 156). The tables keep their names (db_table), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations


class Migration(migrations.Migration):
    # After every migration that names these models the old way (the patient's city, state and
    # marital status): renamed before them, those would point to models that no longer exist.
    dependencies = [
        ("reference_data", "0004_ordem_alfabetica"),
        ("patients", "0007_documento_do_pais"),
    ]

    operations = [
        migrations.AlterModelTable(name="UF", table="referencias_uf"),
        migrations.AlterModelTable(name="Cidade", table="referencias_cidade"),
        migrations.AlterModelTable(name="Banco", table="referencias_banco"),
        migrations.AlterModelTable(name="EstadoCivil", table="referencias_estadocivil"),
        migrations.AlterModelTable(name="Bairro", table="referencias_bairro"),
        migrations.AlterModelTable(name="Logradouro", table="referencias_logradouro"),
        migrations.RenameModel(old_name="UF", new_name="State"),
        migrations.RenameModel(old_name="Cidade", new_name="City"),
        migrations.RenameModel(old_name="Banco", new_name="Bank"),
        migrations.RenameModel(old_name="EstadoCivil", new_name="MaritalStatus"),
        migrations.RenameModel(old_name="Bairro", new_name="Neighborhood"),
        migrations.RenameModel(old_name="Logradouro", new_name="Street"),
    ]
