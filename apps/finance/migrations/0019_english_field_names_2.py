"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0007_english_field_names_1'),
        ('audit', '0003_english_field_names_1'),
        ('account', '0003_english_model_names'),
        ('health_plans', '0005_english_field_names_1'),
        ('core', '0020_english_field_names_1'),
        ('finance', '0018_english_field_names_1'),
        ('estimates', '0005_english_field_names_1'),
        ('patients', '0009_english_field_names_1'),
        ('staff', '0005_english_field_names_1'),
        ('practitioners', '0005_english_field_names_1'),
        ('medical_records', '0005_english_field_names_1'),
        ('recalls', '0003_english_field_names_1'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commission',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='comissoes', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='entry',
            name='paciente',
            field=models.ForeignKey(blank=True, db_column='paciente_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lancamentos', to='patients.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='entry',
            name='profissional',
            field=models.ForeignKey(blank=True, db_column='profissional_id', help_text='Quem fez o atendimento (opcional).', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='profissional',
            new_name='practitioner',
        ),
    ]
