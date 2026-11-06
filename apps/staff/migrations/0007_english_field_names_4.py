"""Field names in English (decision 164). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0009_english_field_names_3'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('finance', '0020_english_field_names_3'),
        ('estimates', '0007_english_field_names_3'),
        ('patients', '0011_english_field_names_3'),
        ('staff', '0006_english_field_names_3'),
        ('practitioners', '0007_english_field_names_3'),
        ('medical_records', '0007_english_field_names_3'),
        ('recalls', '0005_english_field_names_3'),
        ('reference_data', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payroll',
            name='lancamento',
            field=models.OneToOneField(blank=True, db_column='lancamento_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='folha', to='finance.entry', verbose_name='conta a pagar'),
        ),
        migrations.RenameField(
            model_name='payroll',
            old_name='lancamento',
            new_name='entry',
        ),
        migrations.AlterField(
            model_name='salary',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='salário'),
        ),
        migrations.RenameField(
            model_name='salary',
            old_name='valor',
            new_name='amount',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='salary',
                    name='salario_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='salary',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='salario_valor_positivo'),
                ),
            ],
        ),
    ]
