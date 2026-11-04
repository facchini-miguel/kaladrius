"""Field names in English (decision 163). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0008_english_field_names_2'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0005_remove_account_leftovers'),
        ('convenios', '0006_english_field_names_2'),
        ('core', '0021_english_field_names_2'),
        ('financeiro', '0019_english_field_names_2'),
        ('orcamentos', '0006_english_field_names_2'),
        ('pacientes', '0010_english_field_names_2'),
        ('pessoal', '0005_english_field_names_1'),
        ('profissionais', '0006_english_field_names_2'),
        ('prontuario', '0006_english_field_names_2'),
        ('rechamadas', '0004_english_field_names_2'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='twofactor',
            name='ativa',
            field=models.BooleanField(db_column='ativa', default=False, verbose_name='ativa'),
        ),
        migrations.RenameField(
            model_name='twofactor',
            old_name='ativa',
            new_name='active',
        ),
    ]
