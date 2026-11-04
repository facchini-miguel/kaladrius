"""Field names in English (decision 165). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0010_english_field_names_4'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0021_english_field_names_4'),
        ('orcamentos', '0008_english_field_names_4'),
        ('pacientes', '0012_english_field_names_4'),
        ('pessoal', '0007_english_field_names_4'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0008_english_field_names_4'),
        ('rechamadas', '0005_english_field_names_3'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recall',
            name='data',
            field=models.DateField(db_column='data', verbose_name='data'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='data',
            new_name='date',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='recall',
                    name='rechamada_clinica_data',
                ),
                migrations.AddIndex(
                    model_name='recall',
                    index=models.Index(fields=['clinic', 'date'], name='rechamada_clinica_data'),
                ),
                migrations.AlterModelOptions(
                    name='recall',
                    options={'ordering': ['date', 'patient__name'], 'verbose_name': 'rechamada', 'verbose_name_plural': 'rechamadas'},
                ),
            ],
        ),
    ]
