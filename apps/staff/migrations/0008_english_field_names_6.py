"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
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
            model_name='payroll',
            name='funcionario',
            field=models.ForeignKey(db_column='funcionario_id', on_delete=django.db.models.deletion.PROTECT, related_name='folhas', to='pessoal.employee', verbose_name='funcionário'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='funcionario',
            new_name='employee',
        ),
        migrations.AlterField(
            model_name='salary',
            name='funcionario',
            field=models.ForeignKey(db_column='funcionario_id', on_delete=django.db.models.deletion.CASCADE, related_name='salarios', to='pessoal.employee', verbose_name='funcionário'),
        ),
        migrations.RenameField(
            model_name='salary',
            old_name='funcionario',
            new_name='employee',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='payroll',
                    name='folha_unica_por_mes',
                ),
                migrations.AddConstraint(
                    model_name='payroll',
                    constraint=models.UniqueConstraint(fields=('clinic', 'employee', 'competencia'), name='folha_unica_por_mes'),
                ),
                migrations.AlterModelOptions(
                    name='payroll',
                    options={'ordering': ['-competencia', 'employee__name'], 'verbose_name': 'folha do mês', 'verbose_name_plural': 'folhas do mês'},
                ),
            ],
        ),
    ]
