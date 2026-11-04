"""Field names in English (decision 165). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0010_english_field_names_4'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0021_english_field_names_4'),
        ('orcamentos', '0008_english_field_names_4'),
        ('pacientes', '0012_english_field_names_4'),
        ('pessoal', '0007_english_field_names_4'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0008_english_field_names_4'),
        ('rechamadas', '0005_english_field_names_3'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banktransaction',
            name='conta',
            field=models.ForeignKey(db_column='conta_id', on_delete=django.db.models.deletion.PROTECT, related_name='transacoes', to='financeiro.financialaccount', verbose_name='conta'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='conta',
            new_name='account',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='data',
            field=models.DateField(db_column='data', verbose_name='data'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='data',
            new_name='date',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='conta',
            field=models.ForeignKey(db_column='conta_id', on_delete=django.db.models.deletion.PROTECT, related_name='caixas', to='financeiro.financialaccount', verbose_name='conta'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='conta',
            new_name='account',
        ),
        migrations.AlterField(
            model_name='entry',
            name='data',
            field=models.DateField(db_column='data', default=django.utils.timezone.localdate, verbose_name='data'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='data',
            new_name='date',
        ),
        migrations.AlterField(
            model_name='payment',
            name='data',
            field=models.DateField(db_column='data', default=django.utils.timezone.localdate, verbose_name='data'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='data',
            new_name='date',
        ),
        migrations.AlterField(
            model_name='payment',
            name='conta',
            field=models.ForeignKey(db_column='conta_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='financeiro.financialaccount', verbose_name='conta'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='conta',
            new_name='account',
        ),
        migrations.AlterField(
            model_name='statementimport',
            name='conta',
            field=models.ForeignKey(db_column='conta_id', on_delete=django.db.models.deletion.PROTECT, related_name='importacoes', to='financeiro.financialaccount', verbose_name='conta'),
        ),
        migrations.RenameField(
            model_name='statementimport',
            old_name='conta',
            new_name='account',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='banktransaction',
                    name='transacao_unica_por_conta',
                ),
                migrations.AddConstraint(
                    model_name='banktransaction',
                    constraint=models.UniqueConstraint(fields=('account', 'fitid'), name='transacao_unica_por_conta'),
                ),
                migrations.AlterModelOptions(
                    name='banktransaction',
                    options={'ordering': ['date', 'pk'], 'verbose_name': 'transação bancária', 'verbose_name_plural': 'transações bancárias'},
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
                    constraint=models.UniqueConstraint(condition=models.Q(('fechado_em__isnull', True)), fields=('account',), name='um_caixa_aberto_por_conta'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='entry',
                    options={'ordering': ['-date', '-pk'], 'verbose_name': 'lançamento', 'verbose_name_plural': 'lançamentos'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='payment',
                    options={'ordering': ['-date', '-pk'], 'verbose_name': 'pagamento', 'verbose_name_plural': 'pagamentos'},
                ),
            ],
        ),
    ]
