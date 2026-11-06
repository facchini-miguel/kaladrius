"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0006_english_model_names'),
        ('audit', '0002_english_model_names'),
        ('account', '0003_english_model_names'),
        ('health_plans', '0004_english_model_names'),
        ('core', '0019_english_model_names'),
        ('finance', '0017_english_model_names'),
        ('estimates', '0004_english_model_names'),
        ('patients', '0008_english_model_names'),
        ('staff', '0004_english_model_names'),
        ('practitioners', '0004_english_model_names'),
        ('medical_records', '0004_english_model_names'),
        ('recalls', '0002_english_model_names'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountgroup',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='bookclosing',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='bookclosing',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='bookclosing',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='criado por'),
        ),
        migrations.RenameField(
            model_name='bookclosing',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='bookclosing',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='bookclosing',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='criado por'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='cashmovement',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='cashmovement',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='category',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='category',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='commission',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='commission',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='criado por'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='commission',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='commission',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='costcenter',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='costcenter',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='entry',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='entry',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='criado por'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='entry',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='entry',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em', verbose_name='alterado em'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.AlterField(
            model_name='financialaccount',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='financialaccount',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='installment',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='installment',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='payment',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='payment',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='recebido por'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='payment',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='planning',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='planning',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='criado_por',
            field=models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='importado por'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='importado em'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em', verbose_name='alterado em'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='accountgroup',
                    name='grupo_contabil_unico',
                ),
                migrations.AddConstraint(
                    model_name='accountgroup',
                    constraint=models.UniqueConstraint(fields=('clinic', 'tipo', 'pai', 'nome'), name='grupo_contabil_unico'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='bookclosing',
                    options={'ordering': ['-created_at', '-pk'], 'verbose_name': 'fechamento do financeiro', 'verbose_name_plural': 'fechamentos do financeiro'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='cashmovement',
                    options={'ordering': ['created_at'], 'verbose_name': 'movimento de caixa', 'verbose_name_plural': 'movimentos de caixa'},
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'tipo', 'nome'), name='categoria_unica'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='commission',
                    options={'ordering': ['-created_at'], 'verbose_name': 'comissão', 'verbose_name_plural': 'comissões'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='costcenter',
                    name='centro_custo_unico',
                ),
                migrations.AddConstraint(
                    model_name='costcenter',
                    constraint=models.UniqueConstraint(fields=('clinic', 'nome'), name='centro_custo_unico'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='financialaccount',
                    name='conta_unica',
                ),
                migrations.AddConstraint(
                    model_name='financialaccount',
                    constraint=models.UniqueConstraint(fields=('clinic', 'nome'), name='conta_unica'),
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
                    index=models.Index(fields=['clinic', 'vencimento'], name='parcela_clinica_vencimento'),
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'ano', 'grupo'), name='planejamento_unico_por_grupo'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='statementimport',
                    options={'ordering': ['-created_at'], 'verbose_name': 'importação de extrato', 'verbose_name_plural': 'importações de extrato'},
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
                    constraint=models.UniqueConstraint(condition=models.Q(('cpf_cnpj', ''), _negated=True), fields=('clinic', 'cpf_cnpj'), name='fornecedor_cpf_cnpj_unico_por_clinica'),
                ),
            ],
        ),
    ]
