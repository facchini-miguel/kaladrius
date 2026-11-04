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
            model_name='estimate',
            name='observacoes',
            field=models.TextField(blank=True, db_column='observacoes', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='observacoes',
            new_name='notes',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='descricao',
            field=models.CharField(db_column='descricao', max_length=200, verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='descricao',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='estimateitem',
            name='codigo',
            field=models.CharField(blank=True, db_column='codigo', max_length=20, verbose_name='código'),
        ),
        migrations.RenameField(
            model_name='estimateitem',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='procedure',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=120, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='procedure',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='procedure',
            name='codigo',
            field=models.CharField(blank=True, db_column='codigo', max_length=20, verbose_name='código'),
        ),
        migrations.RenameField(
            model_name='procedure',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='procedure',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='procedure',
            old_name='ativo',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='procedure',
                    name='procedimento_unico',
                ),
                migrations.AddConstraint(
                    model_name='procedure',
                    constraint=models.UniqueConstraint(fields=('clinic', 'name'), name='procedimento_unico'),
                ),
                migrations.AlterModelOptions(
                    name='procedure',
                    options={'ordering': ['name'], 'verbose_name': 'procedimento', 'verbose_name_plural': 'procedimentos'},
                ),
            ],
        ),
    ]
