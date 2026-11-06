"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0011_english_field_names_6'),
        ('audit', '0005_english_field_names_6'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0008_english_field_names_6'),
        ('core', '0024_english_field_names_9'),
        ('finance', '0024_english_field_names_7'),
        ('estimates', '0010_english_field_names_6'),
        ('patients', '0014_english_field_names_8'),
        ('staff', '0008_english_field_names_6'),
        ('practitioners', '0008_english_field_names_6'),
        ('medical_records', '0011_english_field_names_9'),
        ('recalls', '0006_english_field_names_5'),
        ('reference_data', '0007_english_field_names_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estimate',
            name='decidido_em',
            field=models.DateTimeField(blank=True, db_column='decidido_em', null=True, verbose_name='aprovado ou recusado em'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='decidido_em',
            new_name='decided_at',
        ),
        migrations.AlterField(
            model_name='estimate',
            name='decidido_por',
            field=models.ForeignKey(blank=True, db_column='decidido_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='aprovado ou recusado por'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='decidido_por',
            new_name='decided_by',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='orcamento',
            field=models.ForeignKey(db_column='orcamento_id', on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='estimates.estimate', verbose_name='orçamento'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='orcamento',
            new_name='estimate',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='procedimento',
            field=models.ForeignKey(blank=True, db_column='procedimento_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='estimates.procedure', verbose_name='procedimento'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='procedimento',
            new_name='procedure',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='dentes',
            field=models.CharField(blank=True, db_column='dentes', max_length=200, verbose_name='dentes'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='dentes',
            new_name='teeth',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='quantidade',
            field=models.PositiveSmallIntegerField(db_column='quantidade', default=1, verbose_name='quantidade'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='quantidade',
            new_name='quantity',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='valor_unitario',
            field=models.DecimalField(db_column='valor_unitario', decimal_places=2, max_digits=12, verbose_name='valor unitário'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='valor_unitario',
            new_name='unit_price',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='estimateitem',
                    name='item_quantidade',
                ),
                migrations.AddConstraint(
                    model_name='estimateitem',
                    constraint=models.CheckConstraint(condition=models.Q(('quantity__gte', 1)), name='item_quantidade'),
                ),
                migrations.RemoveConstraint(
                    model_name='estimateitem',
                    name='item_valor',
                ),
                migrations.AddConstraint(
                    model_name='estimateitem',
                    constraint=models.CheckConstraint(condition=models.Q(('unit_price__gte', 0)), name='item_valor'),
                ),
            ],
        ),
        # The entry's reverse accessor (entry.estimate): state only, no SQL.
        migrations.AlterField(
            model_name="estimate",
            name="entry",
            field=models.OneToOneField(
                blank=True,
                db_column="lancamento_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="estimate",
                to="finance.entry",
                verbose_name="lançamento a receber",
            ),
        ),
    ]
