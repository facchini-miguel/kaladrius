"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0011_english_field_names_6'),
        ('auditoria', '0005_english_field_names_6'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0008_english_field_names_6'),
        ('core', '0024_english_field_names_9'),
        ('financeiro', '0024_english_field_names_7'),
        ('orcamentos', '0010_english_field_names_6'),
        ('pacientes', '0014_english_field_names_8'),
        ('pessoal', '0008_english_field_names_6'),
        ('profissionais', '0008_english_field_names_6'),
        ('prontuario', '0011_english_field_names_9'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0007_english_field_names_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='cpf',
            field=models.CharField(blank=True, db_column='cpf', max_length=20, verbose_name='documento'),
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='cpf',
            new_name='tax_id',
        ),
        migrations.AlterField(
            model_name='employee',
            name='cargo',
            field=models.CharField(blank=True, db_column='cargo', max_length=100, verbose_name='cargo'),
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='cargo',
            new_name='job_title',
        ),
        migrations.AlterField(
            model_name='employee',
            name='admissao',
            field=models.DateField(blank=True, db_column='admissao', null=True, verbose_name='admissão'),
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='admissao',
            new_name='hired_on',
        ),
        migrations.AlterField(
            model_name='employee',
            name='desligamento',
            field=models.DateField(blank=True, db_column='desligamento', null=True, verbose_name='desligamento'),
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='desligamento',
            new_name='left_on',
        ),
        migrations.AlterField(
            model_name='payroll',
            name='competencia',
            field=models.DateField(db_column='competencia', help_text='O primeiro dia do mês.', verbose_name='competência'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='competencia',
            new_name='period',
        ),
        migrations.AlterField(
            model_name='payroll',
            name='salario',
            field=models.DecimalField(db_column='salario', decimal_places=2, max_digits=12, verbose_name='salário'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='salario',
            new_name='salary',
        ),
        migrations.AlterField(
            model_name='payroll',
            name='horas_extras',
            field=models.DecimalField(db_column='horas_extras', decimal_places=2, default=Decimal('0'), max_digits=6, verbose_name='horas extras'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='horas_extras',
            new_name='overtime_hours',
        ),
        migrations.AlterField(
            model_name='payroll',
            name='valor_hora_extra',
            field=models.DecimalField(db_column='valor_hora_extra', decimal_places=2, default=Decimal('0'), max_digits=12, verbose_name='valor da hora extra'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='valor_hora_extra',
            new_name='overtime_rate',
        ),
        migrations.AlterField(
            model_name='payroll',
            name='faltas',
            field=models.PositiveSmallIntegerField(db_column='faltas', default=0, verbose_name='dias de falta'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='faltas',
            new_name='absences',
        ),
        migrations.AlterField(
            model_name='salary',
            name='desde',
            field=models.DateField(db_column='desde', verbose_name='desde'),
        ),
        migrations.RenameField(
            model_name='salary',
            old_name='desde',
            new_name='effective_from',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='employee',
                    name='funcionario_cpf_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='employee',
                    constraint=models.UniqueConstraint(condition=models.Q(('tax_id', ''), _negated=True), fields=('clinic', 'tax_id'), name='funcionario_cpf_unico_por_clinica'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='payroll',
                    name='folha_unica_por_mes',
                ),
                migrations.AddConstraint(
                    model_name='payroll',
                    constraint=models.UniqueConstraint(fields=('clinic', 'employee', 'period'), name='folha_unica_por_mes'),
                ),
                migrations.RemoveConstraint(
                    model_name='payroll',
                    name='folha_competencia_dia_1',
                ),
                migrations.AddConstraint(
                    model_name='payroll',
                    constraint=models.CheckConstraint(condition=models.Q(('period__day', 1)), name='folha_competencia_dia_1'),
                ),
                migrations.AlterModelOptions(
                    name='payroll',
                    options={'ordering': ['-period', 'employee__name'], 'verbose_name': 'folha do mês', 'verbose_name_plural': 'folhas do mês'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='salary',
                    options={'ordering': ['-effective_from', '-pk'], 'verbose_name': 'salário', 'verbose_name_plural': 'salários'},
                ),
            ],
        ),
    ]
