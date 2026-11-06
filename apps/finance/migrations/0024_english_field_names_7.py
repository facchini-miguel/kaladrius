"""Field names in English (decision 167). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0011_english_field_names_6'),
        ('audit', '0005_english_field_names_6'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0008_english_field_names_6'),
        ('core', '0023_english_field_names_6'),
        ('finance', '0023_english_field_names_6'),
        ('estimates', '0010_english_field_names_6'),
        ('patients', '0013_english_field_names_6'),
        ('staff', '0008_english_field_names_6'),
        ('practitioners', '0008_english_field_names_6'),
        ('medical_records', '0010_english_field_names_6'),
        ('recalls', '0006_english_field_names_5'),
        ('reference_data', '0007_english_field_names_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountgroup',
            name='pai',
            field=models.ForeignKey(blank=True, db_column='pai_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='filhos', to='finance.accountgroup', verbose_name='grupo acima'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='pai',
            new_name='parent',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='importacao',
            field=models.ForeignKey(db_column='importacao_id', on_delete=django.db.models.deletion.PROTECT, related_name='transacoes', to='finance.statementimport', verbose_name='importação'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='importacao',
            new_name='statement_import',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='pagamento',
            field=models.OneToOneField(blank=True, db_column='pagamento_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transacao', to='finance.payment', verbose_name='pagamento'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='pagamento',
            new_name='payment',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='movimento',
            field=models.OneToOneField(blank=True, db_column='movimento_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transacao', to='finance.cashmovement', verbose_name='movimento do caixa'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='movimento',
            new_name='cash_movement',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='conciliado_por',
            field=models.ForeignKey(blank=True, db_column='conciliado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='conciliado por'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='conciliado_por',
            new_name='reconciled_by',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='conciliado_em',
            field=models.DateTimeField(blank=True, db_column='conciliado_em', null=True, verbose_name='conciliado em'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='conciliado_em',
            new_name='reconciled_at',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='caixa',
            field=models.ForeignKey(db_column='caixa_id', on_delete=django.db.models.deletion.PROTECT, related_name='movimentos', to='finance.cashregister', verbose_name='caixa'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='caixa',
            new_name='cash_register',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='outra_conta',
            field=models.ForeignKey(blank=True, db_column='outra_conta_id', help_text='Para onde vai a retirada ou de onde vem o reforço (vazio: fora do sistema).', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='finance.financialaccount', verbose_name='outra conta'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='outra_conta',
            new_name='other_account',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='aberto_em',
            field=models.DateTimeField(db_column='aberto_em', default=django.utils.timezone.now, verbose_name='aberto em'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='aberto_em',
            new_name='opened_at',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='aberto_por',
            field=models.ForeignKey(db_column='aberto_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='aberto por'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='aberto_por',
            new_name='opened_by',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='valor_abertura',
            field=models.DecimalField(db_column='valor_abertura', decimal_places=2, max_digits=12, verbose_name='valor contado na abertura'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='valor_abertura',
            new_name='opening_amount',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='fechado_em',
            field=models.DateTimeField(blank=True, db_column='fechado_em', null=True, verbose_name='fechado em'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='fechado_em',
            new_name='closed_at',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='fechado_por',
            field=models.ForeignKey(blank=True, db_column='fechado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='fechado por'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='fechado_por',
            new_name='closed_by',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='valor_esperado',
            field=models.DecimalField(blank=True, db_column='valor_esperado', decimal_places=2, max_digits=12, null=True, verbose_name='valor esperado'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='valor_esperado',
            new_name='expected_amount',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='valor_contado',
            field=models.DecimalField(blank=True, db_column='valor_contado', decimal_places=2, max_digits=12, null=True, verbose_name='valor contado no fechamento'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='valor_contado',
            new_name='counted_amount',
        ),
        migrations.AlterField(
            model_name='commission',
            name='percentual',
            field=models.DecimalField(db_column='percentual', decimal_places=2, max_digits=5, verbose_name='percentual'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='percentual',
            new_name='percentage',
        ),
        migrations.AlterField(
            model_name='commission',
            name='recebido',
            field=models.DecimalField(db_column='recebido', decimal_places=2, max_digits=12, verbose_name='valor recebido'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='recebido',
            new_name='received_amount',
        ),
        migrations.AlterField(
            model_name='commission',
            name='estornos',
            field=models.DecimalField(db_column='estornos', decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='comissão de estornos descontada'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='estornos',
            new_name='reversal_deduction',
        ),
        migrations.AlterField(
            model_name='commission',
            name='cancelada',
            field=models.BooleanField(db_column='cancelada', default=False, verbose_name='cancelada'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='cancelada',
            new_name='cancelled',
        ),
        migrations.AlterField(
            model_name='entry',
            name='centro_custo',
            field=models.ForeignKey(blank=True, db_column='centro_custo_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lancamentos', to='finance.costcenter', verbose_name='centro de custo'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='centro_custo',
            new_name='cost_center',
        ),
        migrations.AlterField(
            model_name='entry',
            name='pessoa',
            field=models.CharField(blank=True, db_column='pessoa', max_length=200, verbose_name='pagador'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='pessoa',
            new_name='payer',
        ),
        migrations.AlterField(
            model_name='entry',
            name='fornecedor',
            field=models.ForeignKey(blank=True, db_column='fornecedor_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lancamentos', to='finance.supplier', verbose_name='fornecedor'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='fornecedor',
            new_name='supplier',
        ),
        migrations.AlterField(
            model_name='entry',
            name='valor_total',
            field=models.DecimalField(db_column='valor_total', decimal_places=2, max_digits=12, verbose_name='valor total'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='valor_total',
            new_name='total_amount',
        ),
        migrations.AlterField(
            model_name='entry',
            name='cancelado',
            field=models.BooleanField(db_column='cancelado', default=False, verbose_name='cancelado'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='cancelado',
            new_name='cancelled',
        ),
        migrations.AlterField(
            model_name='entry',
            name='cancelado_em',
            field=models.DateTimeField(blank=True, db_column='cancelado_em', null=True, verbose_name='cancelado em'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='cancelado_em',
            new_name='cancelled_at',
        ),
        migrations.AlterField(
            model_name='entry',
            name='cancelado_por',
            field=models.ForeignKey(blank=True, db_column='cancelado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='cancelado por'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='cancelado_por',
            new_name='cancelled_by',
        ),
        migrations.AlterField(
            model_name='entry',
            name='motivo_cancelamento',
            field=models.CharField(blank=True, db_column='motivo_cancelamento', max_length=200, verbose_name='motivo do cancelamento'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='motivo_cancelamento',
            new_name='cancellation_reason',
        ),
        migrations.AlterField(
            model_name='financialaccount',
            name='saldo_inicial',
            field=models.DecimalField(db_column='saldo_inicial', decimal_places=2, default=Decimal('0.00'), help_text='Quanto havia na conta antes do primeiro lançamento no sistema.', max_digits=12, verbose_name='saldo inicial'),
        ),
        migrations.RenameField(
            model_name='financialaccount',
            old_name='saldo_inicial',
            new_name='opening_balance',
        ),
        migrations.AlterField(
            model_name='installment',
            name='vencimento',
            field=models.DateField(db_column='vencimento', verbose_name='vencimento'),
        ),
        migrations.RenameField(
            model_name='installment',
            old_name='vencimento',
            new_name='due_date',
        ),
        migrations.AlterField(
            model_name='payment',
            name='parcela',
            field=models.ForeignKey(db_column='parcela_id', on_delete=django.db.models.deletion.PROTECT, related_name='pagamentos', to='finance.installment', verbose_name='parcela'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='parcela',
            new_name='installment',
        ),
        migrations.AlterField(
            model_name='payment',
            name='juros',
            field=models.DecimalField(db_column='juros', decimal_places=2, default=Decimal('0.00'), help_text='Já incluídos no valor recebido.', max_digits=12, verbose_name='juros e multa'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='juros',
            new_name='interest',
        ),
        migrations.AlterField(
            model_name='payment',
            name='forma',
            field=models.CharField(choices=[('dinheiro', 'Dinheiro'), ('pix', 'Pix'), ('debito', 'Cartão de débito'), ('credito', 'Cartão de crédito'), ('transferencia', 'Transferência'), ('boleto', 'Boleto'), ('cheque', 'Cheque'), ('carteira', 'Carteira digital'), ('debito_auto', 'Débito automático'), ('hsa', 'Cartão HSA/FSA'), ('financiamento', 'Financiamento ao paciente'), ('bpay', 'BPAY')], db_column='forma', max_length=15, verbose_name='forma de pagamento'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='forma',
            new_name='method',
        ),
        migrations.AlterField(
            model_name='payment',
            name='cartao_bandeira',
            field=models.CharField(blank=True, db_column='cartao_bandeira', max_length=30, verbose_name='bandeira do cartão'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='cartao_bandeira',
            new_name='card_brand',
        ),
        migrations.AlterField(
            model_name='payment',
            name='cartao_parcelas',
            field=models.PositiveSmallIntegerField(blank=True, db_column='cartao_parcelas', null=True, verbose_name='parcelas no cartão'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='cartao_parcelas',
            new_name='card_installments',
        ),
        migrations.AlterField(
            model_name='payment',
            name='cartao_codigo',
            field=models.CharField(blank=True, db_column='cartao_codigo', max_length=40, verbose_name='código da transação (NSU)'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='cartao_codigo',
            new_name='card_transaction_code',
        ),
        migrations.AlterField(
            model_name='payment',
            name='estornado',
            field=models.BooleanField(db_column='estornado', default=False, verbose_name='estornado'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='estornado',
            new_name='reversed',
        ),
        migrations.AlterField(
            model_name='payment',
            name='estornado_em',
            field=models.DateTimeField(blank=True, db_column='estornado_em', null=True, verbose_name='estornado em'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='estornado_em',
            new_name='reversed_at',
        ),
        migrations.AlterField(
            model_name='payment',
            name='estornado_por',
            field=models.ForeignKey(blank=True, db_column='estornado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='estornado por'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='estornado_por',
            new_name='reversed_by',
        ),
        migrations.AlterField(
            model_name='payment',
            name='motivo_estorno',
            field=models.CharField(blank=True, db_column='motivo_estorno', max_length=200, verbose_name='motivo do estorno'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='motivo_estorno',
            new_name='reversal_reason',
        ),
        migrations.AlterField(
            model_name='payment',
            name='comissao',
            field=models.ForeignKey(blank=True, db_column='comissao_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pagamentos', to='finance.commission', verbose_name='comissão'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='comissao',
            new_name='commission',
        ),
        migrations.AlterField(
            model_name='payment',
            name='comissao_estorno',
            field=models.ForeignKey(blank=True, db_column='comissao_estorno_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pagamentos_estornados', to='finance.commission', verbose_name='comissão que descontou o estorno'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='comissao_estorno',
            new_name='commission_reversal',
        ),
        migrations.AlterField(
            model_name='planning',
            name='ano',
            field=models.PositiveSmallIntegerField(db_column='ano', verbose_name='ano'),
        ),
        migrations.RenameField(
            model_name='planning',
            old_name='ano',
            new_name='year',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='banco',
            field=models.CharField(blank=True, db_column='banco', max_length=20, verbose_name='código do banco'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='banco',
            new_name='bank_code',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='conta_no_banco',
            field=models.CharField(blank=True, db_column='conta_no_banco', max_length=40, verbose_name='conta no banco'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='conta_no_banco',
            new_name='bank_account_number',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='saldo',
            field=models.DecimalField(blank=True, db_column='saldo', decimal_places=2, max_digits=12, null=True, verbose_name='saldo no banco'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='saldo',
            new_name='balance',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='saldo_em',
            field=models.DateField(blank=True, db_column='saldo_em', null=True, verbose_name='saldo em'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='saldo_em',
            new_name='balance_date',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='novas',
            field=models.PositiveIntegerField(db_column='novas', default=0, verbose_name='transações novas'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='novas',
            new_name='new_transactions',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='repetidas',
            field=models.PositiveIntegerField(db_column='repetidas', default=0, verbose_name='transações já importadas'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='repetidas',
            new_name='duplicate_transactions',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='ignoradas',
            field=models.PositiveIntegerField(db_column='ignoradas', default=0, help_text='Linhas do arquivo sem data ou valor que dê para ler: não foram importadas.', verbose_name='transações ilegíveis'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='ignoradas',
            new_name='unreadable_transactions',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='accountgroup',
                    name='grupo_contabil_unico',
                ),
                migrations.AddConstraint(
                    model_name='accountgroup',
                    constraint=models.UniqueConstraint(fields=('clinic', 'kind', 'parent', 'name'), name='grupo_contabil_unico'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='banktransaction',
                    name='transacao_um_vinculo',
                ),
                migrations.AddConstraint(
                    model_name='banktransaction',
                    constraint=models.CheckConstraint(condition=models.Q(('cash_movement__isnull', False), ('payment__isnull', False), _negated=True), name='transacao_um_vinculo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='cashregister',
                    name='um_caixa_aberto_por_conta',
                ),
                migrations.AddConstraint(
                    model_name='cashregister',
                    constraint=models.UniqueConstraint(condition=models.Q(('closed_at__isnull', True)), fields=('account',), name='um_caixa_aberto_por_conta'),
                ),
                migrations.RemoveConstraint(
                    model_name='cashregister',
                    name='caixa_abertura_positiva',
                ),
                migrations.AddConstraint(
                    model_name='cashregister',
                    constraint=models.CheckConstraint(condition=models.Q(('opening_amount__gte', 0)), name='caixa_abertura_positiva'),
                ),
                migrations.AlterModelOptions(
                    name='cashregister',
                    options={'ordering': ['-opened_at'], 'verbose_name': 'caixa', 'verbose_name_plural': 'caixas'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='entry',
                    name='lancamento_valor_positivo',
                ),
                migrations.AddConstraint(
                    model_name='entry',
                    constraint=models.CheckConstraint(condition=models.Q(('total_amount__gt', 0)), name='lancamento_valor_positivo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='installment',
                    name='parcela_clinica_vencimento',
                ),
                migrations.AddIndex(
                    model_name='installment',
                    index=models.Index(fields=['clinic', 'due_date'], name='parcela_clinica_vencimento'),
                ),
                migrations.AlterModelOptions(
                    name='installment',
                    options={'ordering': ['due_date', 'number'], 'verbose_name': 'parcela', 'verbose_name_plural': 'parcelas'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='payment',
                    name='pagamento_juros_positivo',
                ),
                migrations.AddConstraint(
                    model_name='payment',
                    constraint=models.CheckConstraint(condition=models.Q(('interest__gte', 0)), name='pagamento_juros_positivo'),
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'year', 'group'), name='planejamento_unico_por_grupo'),
                ),
                migrations.AlterModelOptions(
                    name='planning',
                    options={'ordering': ['year', 'group'], 'verbose_name': 'meta do planejamento', 'verbose_name_plural': 'metas do planejamento'},
                ),
            ],
        ),
        # The entry's reverse accessor (entry.commission): state only, no SQL.
        migrations.AlterField(
            model_name="commission",
            name="entry",
            field=models.OneToOneField(
                db_column="lancamento_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="commission",
                to="finance.entry",
                verbose_name="lançamento a pagar",
            ),
        ),
    ]
