"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import apps.estimates.models
import django.db.models.deletion
from decimal import Decimal
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
            model_name='estimate',
            name='validade',
            field=models.DateField(db_column='validade', default=apps.estimates.models.validade_padrao, verbose_name='válido até'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='validade',
            new_name='valid_until',
        ),
        migrations.AlterField(
            model_name='estimate',
            name='desconto',
            field=models.DecimalField(db_column='desconto', decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='desconto'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='desconto',
            new_name='discount',
        ),
        migrations.AlterField(
            model_name='procedure',
            name='categoria',
            field=models.ForeignKey(blank=True, db_column='categoria_id', help_text='Categoria de receita usada quando o orçamento é aprovado.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='finance.category', verbose_name='categoria'),
        ),
        migrations.RenameField(
            model_name='procedure',
            old_name='categoria',
            new_name='category',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='estimate',
                    name='orcamento_desconto',
                ),
                migrations.AddConstraint(
                    model_name='estimate',
                    constraint=models.CheckConstraint(condition=models.Q(('discount__gte', 0)), name='orcamento_desconto'),
                ),
            ],
        ),
    ]
