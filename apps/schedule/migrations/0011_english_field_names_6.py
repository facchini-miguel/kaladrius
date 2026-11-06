"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import apps.schedule.models
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0010_english_field_names_4'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('finance', '0022_english_field_names_5'),
        ('estimates', '0009_english_field_names_5'),
        ('patients', '0012_english_field_names_4'),
        ('staff', '0007_english_field_names_4'),
        ('practitioners', '0007_english_field_names_3'),
        ('medical_records', '0009_english_field_names_5'),
        ('recalls', '0006_english_field_names_5'),
        ('reference_data', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='inicio',
            field=models.DateTimeField(db_column='inicio', verbose_name='início'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='inicio',
            new_name='start',
        ),
        migrations.AlterField(
            model_name='appointment',
            name='fim',
            field=models.DateTimeField(db_column='fim', verbose_name='fim'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='fim',
            new_name='end',
        ),
        migrations.AlterField(
            model_name='appointmenttype',
            name='cor',
            field=models.CharField(db_column='cor', default='#0d6efd', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', 'Use uma cor no formato #RRGGBB.')], verbose_name='cor'),
        ),
        migrations.RenameField(
            model_name='appointmenttype',
            old_name='cor',
            new_name='color',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='appointment',
                    name='agendamento_prof_inicio',
                ),
                migrations.AddIndex(
                    model_name='appointment',
                    index=models.Index(fields=['clinic', 'practitioner', 'start'], name='agendamento_prof_inicio'),
                ),
                migrations.RemoveConstraint(
                    model_name='appointment',
                    name='agendamento_inicio_antes_do_fim',
                ),
                migrations.AddConstraint(
                    model_name='appointment',
                    constraint=models.CheckConstraint(condition=models.Q(('start__lt', models.F('end'))), name='agendamento_inicio_antes_do_fim'),
                ),
                migrations.RemoveConstraint(
                    model_name='appointment',
                    name='agendamento_sem_sobreposicao',
                ),
                migrations.AddConstraint(
                    model_name='appointment',
                    constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status', 'desmarcou'), _negated=True), expressions=[(apps.schedule.models.TsTzRange('start', 'end', django.contrib.postgres.fields.ranges.RangeBoundary()), '&&'), ('practitioner', '=')], name='agendamento_sem_sobreposicao', violation_error_message='O profissional já tem um agendamento neste horário.'),
                ),
                migrations.AlterModelOptions(
                    name='appointment',
                    options={'ordering': ['start'], 'verbose_name': 'agendamento', 'verbose_name_plural': 'agendamentos'},
                ),
            ],
        ),
    ]
