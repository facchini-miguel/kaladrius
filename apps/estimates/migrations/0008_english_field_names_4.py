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
            model_name='estimate',
            name='situacao',
            field=models.CharField(choices=[('aberto', 'Em aberto'), ('aprovado', 'Aprovado'), ('recusado', 'Recusado')], db_column='situacao', default='aberto', max_length=10, verbose_name='situação'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='situacao',
            new_name='status',
        ),
        migrations.AlterField(
            model_name='estimate',
            name='lancamento',
            field=models.OneToOneField(blank=True, db_column='lancamento_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orcamento', to='finance.entry', verbose_name='lançamento a receber'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='lancamento',
            new_name='entry',
        ),
        migrations.AlterField(
            model_name='procedure',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='valor'),
        ),
        migrations.RenameField(
            model_name='procedure',
            old_name='valor',
            new_name='amount',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='procedure',
                    name='procedimento_valor',
                ),
                migrations.AddConstraint(
                    model_name='procedure',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gte', 0)), name='procedimento_valor'),
                ),
            ],
        ),
    ]
