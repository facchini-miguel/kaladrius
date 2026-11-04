"""Field names in English (decision 163). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0008_english_field_names_2'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0005_remove_account_leftovers'),
        ('convenios', '0006_english_field_names_2'),
        ('core', '0021_english_field_names_2'),
        ('financeiro', '0019_english_field_names_2'),
        ('orcamentos', '0006_english_field_names_2'),
        ('pacientes', '0010_english_field_names_2'),
        ('pessoal', '0005_english_field_names_1'),
        ('profissionais', '0006_english_field_names_2'),
        ('prontuario', '0006_english_field_names_2'),
        ('rechamadas', '0004_english_field_names_2'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bank',
            name='codigo',
            field=models.PositiveSmallIntegerField(blank=True, db_column='codigo', null=True, unique=True, verbose_name='código'),
        ),
        migrations.RenameField(
            model_name='bank',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='bank',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='bank',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='city',
            name='codigo',
            field=models.PositiveIntegerField(db_column='codigo', primary_key=True, serialize=False, verbose_name='código IBGE'),
        ),
        migrations.RenameField(
            model_name='city',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='city',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=100, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='city',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='maritalstatus',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=30, unique=True, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='maritalstatus',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='neighborhood',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=100, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='neighborhood',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='state',
            name='codigo',
            field=models.PositiveSmallIntegerField(db_column='codigo', primary_key=True, serialize=False, verbose_name='código IBGE'),
        ),
        migrations.RenameField(
            model_name='state',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='state',
            name='nome',
            field=models.CharField(db_column='nome', max_length=50, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='state',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='street',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='street',
            old_name='nome',
            new_name='name',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='bank',
                    options={'ordering': [models.OrderBy(models.F('code'), nulls_last=True), 'name'], 'verbose_name': 'banco', 'verbose_name_plural': 'bancos'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='city',
                    name='cidade_uf_nome',
                ),
                migrations.AddIndex(
                    model_name='city',
                    index=models.Index(fields=['uf', 'name'], name='cidade_uf_nome'),
                ),
                migrations.AlterModelOptions(
                    name='city',
                    options={'ordering': ['name'], 'verbose_name': 'cidade', 'verbose_name_plural': 'cidades'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='maritalstatus',
                    options={'ordering': ['ordem', 'name'], 'verbose_name': 'estado civil', 'verbose_name_plural': 'estados civis'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='neighborhood',
                    name='bairro_unico_por_cidade',
                ),
                migrations.AddConstraint(
                    model_name='neighborhood',
                    constraint=models.UniqueConstraint(fields=('cidade', 'name'), name='bairro_unico_por_cidade'),
                ),
                migrations.AlterModelOptions(
                    name='neighborhood',
                    options={'ordering': ['name'], 'verbose_name': 'bairro', 'verbose_name_plural': 'bairros'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='street',
                    name='logradouro_unico_por_bairro',
                ),
                migrations.AddConstraint(
                    model_name='street',
                    constraint=models.UniqueConstraint(fields=('cidade', 'bairro', 'name'), name='logradouro_unico_por_bairro'),
                ),
                migrations.AlterModelOptions(
                    name='street',
                    options={'ordering': ['name'], 'verbose_name': 'logradouro', 'verbose_name_plural': 'logradouros'},
                ),
            ],
        ),
    ]
