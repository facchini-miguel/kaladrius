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
            model_name='addendum',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='visit',
            name='paciente',
            field=models.ForeignKey(db_column='paciente_id', on_delete=django.db.models.deletion.PROTECT, related_name='atendimentos', to='patients.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='visit',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='atendimentos', to='practitioners.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='profissional',
            new_name='practitioner',
        ),
    ]
