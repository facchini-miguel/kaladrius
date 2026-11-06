"""Field names in English (decision 163). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0008_english_field_names_2'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0005_remove_account_leftovers'),
        ('health_plans', '0006_english_field_names_2'),
        ('core', '0021_english_field_names_2'),
        ('finance', '0019_english_field_names_2'),
        ('estimates', '0006_english_field_names_2'),
        ('patients', '0010_english_field_names_2'),
        ('staff', '0005_english_field_names_1'),
        ('practitioners', '0006_english_field_names_2'),
        ('medical_records', '0006_english_field_names_2'),
        ('recalls', '0004_english_field_names_2'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountgroup',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=60, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='accountgroup',
            name='codigo',
            field=models.PositiveSmallIntegerField(blank=True, db_column='codigo', help_text='Posição dentro do grupo acima (1, 2, 3…); forma números como 2.1.', null=True, verbose_name='código'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='accountgroup',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='accountgroup',
            old_name='ativo',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='descricao',
            field=models.CharField(blank=True, db_column='descricao', max_length=200, verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='banktransaction',
            old_name='descricao',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='cashregister',
            name='observacao',
            field=models.CharField(blank=True, db_column='observacao', max_length=200, verbose_name='observação'),
        ),
        migrations.RenameField(
            model_name='cashregister',
            old_name='observacao',
            new_name='note',
        ),
        migrations.AlterField(
            model_name='category',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=60, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='category',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='category',
            name='ativa',
            field=models.BooleanField(db_column='ativa', default=True, verbose_name='ativa'),
        ),
        migrations.RenameField(
            model_name='category',
            old_name='ativa',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='costcenter',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=60, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='costcenter',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='costcenter',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='costcenter',
            old_name='ativo',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='entry',
            name='descricao',
            field=models.CharField(db_column='descricao', max_length=200, verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='descricao',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='entry',
            name='observacoes',
            field=models.TextField(blank=True, db_column='observacoes', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='entry',
            old_name='observacoes',
            new_name='notes',
        ),
        migrations.AlterField(
            model_name='financialaccount',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=60, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='financialaccount',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='financialaccount',
            name='ativa',
            field=models.BooleanField(db_column='ativa', default=True, verbose_name='ativa'),
        ),
        migrations.RenameField(
            model_name='financialaccount',
            old_name='ativa',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='installment',
            name='numero',
            field=models.PositiveSmallIntegerField(db_column='numero', verbose_name='número'),
        ),
        migrations.RenameField(
            model_name='installment',
            old_name='numero',
            new_name='number',
        ),
        migrations.AlterField(
            model_name='payment',
            name='observacao',
            field=models.CharField(blank=True, db_column='observacao', max_length=200, verbose_name='observação'),
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='observacao',
            new_name='note',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', help_text='Para pessoa jurídica, o nome fantasia.', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='telefone',
            field=models.CharField(blank=True, db_column='telefone', max_length=11, verbose_name='telefone'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='telefone',
            new_name='phone',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='observacoes',
            field=models.TextField(blank=True, db_column='observacoes', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='observacoes',
            new_name='notes',
        ),
        migrations.AlterField(
            model_name='supplier',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='supplier',
            old_name='ativo',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='accountgroup',
                    name='grupo_contabil_unico',
                ),
                migrations.AddConstraint(
                    model_name='accountgroup',
                    constraint=models.UniqueConstraint(fields=('clinic', 'tipo', 'pai', 'name'), name='grupo_contabil_unico'),
                ),
                migrations.AlterModelOptions(
                    name='accountgroup',
                    options={'ordering': ['tipo', 'code', 'name'], 'verbose_name': 'grupo contábil', 'verbose_name_plural': 'grupos contábeis'},
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'tipo', 'name'), name='categoria_unica'),
                ),
                migrations.AlterModelOptions(
                    name='category',
                    options={'ordering': ['tipo', 'name'], 'verbose_name': 'categoria', 'verbose_name_plural': 'categorias'},
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'name'), name='centro_custo_unico'),
                ),
                migrations.AlterModelOptions(
                    name='costcenter',
                    options={'ordering': ['name'], 'verbose_name': 'centro de custo', 'verbose_name_plural': 'centros de custo'},
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
                    constraint=models.UniqueConstraint(fields=('clinic', 'name'), name='conta_unica'),
                ),
                migrations.AlterModelOptions(
                    name='financialaccount',
                    options={'ordering': ['name'], 'verbose_name': 'conta', 'verbose_name_plural': 'contas'},
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
                    constraint=models.UniqueConstraint(fields=('lancamento', 'number'), name='parcela_numero_unico'),
                ),
                migrations.AlterModelOptions(
                    name='installment',
                    options={'ordering': ['vencimento', 'number'], 'verbose_name': 'parcela', 'verbose_name_plural': 'parcelas'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='supplier',
                    options={'ordering': ['name'], 'verbose_name': 'fornecedor', 'verbose_name_plural': 'fornecedores'},
                ),
            ],
        ),
    ]
