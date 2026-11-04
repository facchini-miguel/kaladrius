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
            model_name='addendum',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='visit',
            name='paciente',
            field=models.ForeignKey(db_column='paciente_id', on_delete=django.db.models.deletion.PROTECT, related_name='atendimentos', to='pacientes.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='visit',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='atendimentos', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='profissional',
            new_name='practitioner',
        ),
    ]
