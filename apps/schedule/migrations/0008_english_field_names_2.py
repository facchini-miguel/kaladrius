"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import apps.schedule.models
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
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
            model_name='appointment',
            name='profissional',
            field=models.ForeignKey(db_column='profissional_id', on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='profissionais.practitioner', verbose_name='profissional'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='profissional',
            new_name='practitioner',
        ),
        migrations.AlterField(
            model_name='appointment',
            name='paciente',
            field=models.ForeignKey(blank=True, db_column='paciente_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='pacientes.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='appointment',
                    name='agendamento_prof_inicio',
                ),
                migrations.AddIndex(
                    model_name='appointment',
                    index=models.Index(fields=['clinic', 'practitioner', 'inicio'], name='agendamento_prof_inicio'),
                ),
                migrations.RemoveConstraint(
                    model_name='appointment',
                    name='agendamento_sem_sobreposicao',
                ),
                migrations.AddConstraint(
                    model_name='appointment',
                    constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('situacao', 'desmarcou'), _negated=True), expressions=[(apps.schedule.models.TsTzRange('inicio', 'fim', django.contrib.postgres.fields.ranges.RangeBoundary()), '&&'), ('practitioner', '=')], name='agendamento_sem_sobreposicao', violation_error_message='O profissional já tem um agendamento neste horário.'),
                ),
            ],
        ),
    ]
