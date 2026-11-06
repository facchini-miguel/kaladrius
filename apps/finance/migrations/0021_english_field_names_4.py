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
            model_name='accountgroup',
            name='tipo',
            field=models.CharField(choices=[('receita', 'Receita'), ('despesa', 'Despesa')], db_column='tipo', max_length=10, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, help_text='Positivo: entrada; negativo: saída.', max_digits=12, verbose_name='valor'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='tipo',
            field=models.CharField(blank=True, db_column='tipo', max_length=20, verbose_name='tipo no banco'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='situacao',
            field=models.CharField(choices=[('pendente', 'Pendente'), ('conciliada', 'Conciliada'), ('ignorada', 'Ignorada')], db_column='situacao', default='pendente', max_length=10, verbose_name='situação'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='situacao',
            new_name='status',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='tipo',
            field=models.CharField(choices=[('retirada', 'Retirada (sangria)'), ('reforco', 'Reforço')], db_column='tipo', max_length=10, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='valor'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='category',
            name='tipo',
            field=models.CharField(choices=[('receita', 'Receita'), ('despesa', 'Despesa')], db_column='tipo', max_length=10, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='category',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='commission',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='valor da comissão'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='commission',
            name='lancamento',
            field=models.OneToOneField(db_column='lancamento_id', on_delete=django.db.models.deletion.PROTECT, related_name='comissao', to='finance.entry', verbose_name='lançamento a pagar'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='lancamento',
            new_name='entry',
        ),
        migrations.AlterField(
            model_name='entry',
            name='tipo',
            field=models.CharField(choices=[('receber', 'A receber'), ('pagar', 'A pagar')], db_column='tipo', max_length=10, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='financialaccount',
            name='tipo',
            field=models.CharField(choices=[('dinheiro', 'Dinheiro (caixa)'), ('banco', 'Banco'), ('cartao', 'Maquininha de cartão')], db_column='tipo', max_length=10, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='financialaccount',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='installment',
            name='lancamento',
            field=models.ForeignKey(db_column='lancamento_id', on_delete=django.db.models.deletion.CASCADE, related_name='parcelas', to='finance.entry', verbose_name='lançamento'),
        ),
        migrations.RenameField(
            model_name='installment',
            old_name='lancamento',
            new_name='entry',
        ),
        migrations.AlterField(
            model_name='installment',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='valor'),
        ),
        migrations.RenameField(
            model_name='installment',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='payment',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='valor recebido'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='planning',
            name='valor',
            field=models.DecimalField(db_column='valor', decimal_places=2, max_digits=12, verbose_name='meta'),
        ),
        migrations.RenameField(
            model_name='planning',
            old_name='valor',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='tipo',
            field=models.CharField(choices=[('PF', 'Pessoa física'), ('PJ', 'Pessoa jurídica')], db_column='tipo', default='PJ', max_length=2, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='accountgroup',
                    name='grupo_contabil_unico',
                ),
                migrations.AddConstraint(
                    model_name='accountgroup',
                    constraint=models.UniqueConstraint(fields=('clinic', 'kind', 'pai', 'name'), name='grupo_contabil_unico'),
                ),
                migrations.AlterModelOptions(
                    name='accountgroup',
                    options={'ordering': ['kind', 'code', 'name'], 'verbose_name': 'grupo contábil', 'verbose_name_plural': 'grupos contábeis'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='cashmovement',
                    name='movimento_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='cashmovement',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='movimento_valor_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='category',
                    name='categoria_unica',
                ),
                migrations.AddConstraint(
                    model_name='category',
                    constraint=models.UniqueConstraint(fields=('clinic', 'kind', 'name'), name='categoria_unica'),
                ),
                migrations.AlterModelOptions(
                    name='category',
                    options={'ordering': ['kind', 'name'], 'verbose_name': 'categoria', 'verbose_name_plural': 'categorias'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='commission',
                    name='comissao_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='commission',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='comissao_valor_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='installment',
                    name='parcela_numero_unico',
                ),
                migrations.AddConstraint(
                    model_name='installment',
                    constraint=models.UniqueConstraint(fields=('entry', 'number'), name='parcela_numero_unico'),
                ),
                migrations.RemoveConstraint(
                    model_name='installment',
                    name='parcela_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='installment',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='parcela_valor_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='payment',
                    name='pagamento_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='payment',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='pagamento_valor_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='planning',
                    name='planejamento_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='planning',
                    constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='planejamento_valor_positivo'),
                ),
            ],
        ),
    ]
