"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0010_english_field_names_4'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0022_english_field_names_5'),
        ('orcamentos', '0009_english_field_names_5'),
        ('pacientes', '0012_english_field_names_4'),
        ('pessoal', '0007_english_field_names_4'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0009_english_field_names_5'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='practitioner',
            name='registro',
            field=models.CharField(blank=True, db_column='registro', help_text='CRO, CRM, CREFITO, CRP…', max_length=30, verbose_name='registro profissional'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='registro',
            new_name='registration',
        ),
        migrations.AlterField(
            model_name='practitioner',
            name='cor',
            field=models.CharField(db_column='cor', default='#0d6efd', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', 'Use uma cor no formato #RRGGBB.')], verbose_name='cor na agenda'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='cor',
            new_name='color',
        ),
    ]
