"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0007_english_field_names_1'),
        ('auditoria', '0003_english_field_names_1'),
        ('conta', '0003_english_model_names'),
        ('convenios', '0005_english_field_names_1'),
        ('core', '0020_english_field_names_1'),
        ('financeiro', '0018_english_field_names_1'),
        ('orcamentos', '0005_english_field_names_1'),
        ('pacientes', '0009_english_field_names_1'),
        ('pessoal', '0005_english_field_names_1'),
        ('profissionais', '0005_english_field_names_1'),
        ('prontuario', '0005_english_field_names_1'),
        ('rechamadas', '0003_english_field_names_1'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estimate',
            name='paciente',
            field=models.ForeignKey(db_column='paciente_id', on_delete=django.db.models.deletion.PROTECT, related_name='orcamentos', to='pacientes.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='estimate',
            name='profissional',
            field=models.ForeignKey(blank=True, db_column='profissional_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='profissional',
            new_name='practitioner',
        ),
    ]
