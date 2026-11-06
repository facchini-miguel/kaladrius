"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

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
            model_name='banktransaction',
            name='motivo',
            field=models.CharField(blank=True, db_column='motivo', max_length=200, verbose_name='motivo'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='motivo',
            new_name='reason',
        ),
        migrations.AlterField(
            model_name='bookclosing',
            name='ate',
            field=models.DateField(blank=True, db_column='ate', null=True, verbose_name='fechado até'),
        ),
        migrations.RenameField(
            model_name='bookclosing',
            old_name='ate',
            new_name='until',
        ),
        migrations.AlterField(
            model_name='bookclosing',
            name='motivo',
            field=models.CharField(blank=True, db_column='motivo', max_length=200, verbose_name='motivo'),
        ),
        migrations.RenameField(
            model_name='bookclosing',
            old_name='motivo',
            new_name='reason',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='motivo',
            field=models.CharField(db_column='motivo', max_length=200, verbose_name='motivo'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='motivo',
            new_name='reason',
        ),
        migrations.AlterField(
            model_name='category',
            name='grupo',
            field=models.ForeignKey(blank=True, db_column='grupo_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='categorias', to='finance.accountgroup', verbose_name='grupo'),
        ),
        migrations.RenameField(
            model_name='category',
            old_name='grupo',
            new_name='group',
        ),
        migrations.AlterField(
            model_name='commission',
            name='ate',
            field=models.DateField(db_column='ate', verbose_name='recebimentos até'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='ate',
            new_name='until',
        ),
        migrations.AlterField(
            model_name='entry',
            name='categoria',
            field=models.ForeignKey(db_column='categoria_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='finance.category', verbose_name='categoria'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='categoria',
            new_name='category',
        ),
        migrations.AlterField(
            model_name='payment',
            name='desconto',
            field=models.DecimalField(db_column='desconto', decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='desconto'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='desconto',
            new_name='discount',
        ),
        migrations.AlterField(
            model_name='planning',
            name='grupo',
            field=models.ForeignKey(db_column='grupo_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='finance.accountgroup', verbose_name='grupo'),
        ),
        migrations.RenameField(
            model_name='planning',
            old_name='grupo',
            new_name='group',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='arquivo',
            field=models.CharField(db_column='arquivo', max_length=200, verbose_name='arquivo'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='arquivo',
            new_name='file',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='inicio',
            field=models.DateField(blank=True, db_column='inicio', null=True, verbose_name='início'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='inicio',
            new_name='start',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='fim',
            field=models.DateField(blank=True, db_column='fim', null=True, verbose_name='fim'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='fim',
            new_name='end',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='razao_social',
            field=models.CharField(blank=True, db_column='razao_social', max_length=200, verbose_name='razão social'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='razao_social',
            new_name='legal_name',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='cpf_cnpj',
            field=models.CharField(blank=True, db_column='cpf_cnpj', max_length=20, verbose_name='documento'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='cpf_cnpj',
            new_name='tax_id',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='payment',
                    name='pagamento_desconto_positivo',
                ),
                migrations.AddConstraint(
                    model_name='payment',
                    constraint=models.CheckConstraint(condition=models.Q(('discount__gte', 0)), name='pagamento_desconto_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='planning',
                    name='planejamento_unico_por_grupo',
                ),
                migrations.AddConstraint(
                    model_name='planning',
                    constraint=models.UniqueConstraint(fields=('clinic', 'ano', 'group'), name='planejamento_unico_por_grupo'),
                ),
                migrations.AlterModelOptions(
                    name='planning',
                    options={'ordering': ['ano', 'group'], 'verbose_name': 'meta do planejamento', 'verbose_name_plural': 'metas do planejamento'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='supplier',
                    name='fornecedor_cpf_cnpj_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='supplier',
                    constraint=models.UniqueConstraint(condition=models.Q(('tax_id', ''), _negated=True), fields=('clinic', 'tax_id'), name='fornecedor_cpf_cnpj_unico_por_clinica'),
                ),
            ],
        ),
    ]
