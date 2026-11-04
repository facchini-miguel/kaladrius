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
            model_name='recall',
            name='descricao',
            field=models.CharField(db_column='descricao', help_text='Ex.: revisão de 6 meses.', max_length=200, verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='descricao',
            new_name='description',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='recall',
                    options={'ordering': ['data', 'patient__name'], 'verbose_name': 'rechamada', 'verbose_name_plural': 'rechamadas'},
                ),
            ],
        ),
    ]
