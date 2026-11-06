"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
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
            model_name='recall',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='recall',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='criado por'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='recall',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='recall',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em', verbose_name='alterado em'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='recall',
                    name='rechamada_clinica_data',
                ),
                migrations.AddIndex(
                    model_name='recall',
                    index=models.Index(fields=['clinic', 'data'], name='rechamada_clinica_data'),
                ),
            ],
        ),
    ]
