"""Field names in English (decision 164). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import apps.schedule.models
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0009_english_field_names_3'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0020_english_field_names_3'),
        ('orcamentos', '0007_english_field_names_3'),
        ('pacientes', '0011_english_field_names_3'),
        ('pessoal', '0006_english_field_names_3'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0007_english_field_names_3'),
        ('rechamadas', '0005_english_field_names_3'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='tipo',
            field=models.ForeignKey(db_column='tipo_id', on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='agenda.appointmenttype', verbose_name='tipo de atendimento'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='appointment',
            name='situacao',
            field=models.CharField(choices=[('agendado', 'Agendado'), ('compareceu', 'Compareceu'), ('faltou', 'Faltou'), ('desmarcou', 'Desmarcou')], db_column='situacao', default='agendado', max_length=10, verbose_name='situação'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='situacao',
            new_name='status',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='appointment',
                    name='agendamento_sem_sobreposicao',
                ),
                migrations.AddConstraint(
                    model_name='appointment',
                    constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status', 'desmarcou'), _negated=True), expressions=[(apps.schedule.models.TsTzRange('inicio', 'fim', django.contrib.postgres.fields.ranges.RangeBoundary()), '&&'), ('practitioner', '=')], name='agendamento_sem_sobreposicao', violation_error_message='O profissional já tem um agendamento neste horário.'),
                ),
            ],
        ),
    ]
