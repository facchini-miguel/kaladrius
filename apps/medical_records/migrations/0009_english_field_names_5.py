"""Field names in English (decision 165). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.utils.timezone
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
            model_name='certificate',
            name='data',
            field=models.DateField(db_column='data', default=django.utils.timezone.localdate, verbose_name='data do atendimento'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='data',
            new_name='date',
        ),
        migrations.AlterField(
            model_name='visit',
            name='data',
            field=models.DateTimeField(db_column='data', default=django.utils.timezone.now, verbose_name='data do atendimento'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='data',
            new_name='date',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='visit',
                    options={'ordering': ['-date', '-pk'], 'verbose_name': 'atendimento', 'verbose_name_plural': 'atendimentos'},
                ),
            ],
        ),
    ]
