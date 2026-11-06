"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0006_english_model_names'),
        ('audit', '0002_english_model_names'),
        ('account', '0003_english_model_names'),
        ('health_plans', '0004_english_model_names'),
        ('core', '0019_english_model_names'),
        ('finance', '0017_english_model_names'),
        ('estimates', '0004_english_model_names'),
        ('patients', '0008_english_model_names'),
        ('staff', '0004_english_model_names'),
        ('practitioners', '0004_english_model_names'),
        ('medical_records', '0004_english_model_names'),
        ('recalls', '0002_english_model_names'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditentry',
            name='clinica',
            field=models.ForeignKey(blank=True, db_column='clinica_id', db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='auditentry',
                    name='auditoria_clinica_momento',
                ),
                migrations.AddIndex(
                    model_name='auditentry',
                    index=models.Index(fields=['clinic', '-momento'], name='auditoria_clinica_momento'),
                ),
            ],
        ),
    ]
