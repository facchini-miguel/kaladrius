"""Field names in English (decision 163). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.functions.text
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
            model_name='healthplan',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='healthplan',
            name='telefone',
            field=models.CharField(blank=True, db_column='telefone', max_length=11, verbose_name='telefone'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='telefone',
            new_name='phone',
        ),
        migrations.AlterField(
            model_name='healthplan',
            name='observacoes',
            field=models.TextField(blank=True, db_column='observacoes', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='observacoes',
            new_name='notes',
        ),
        migrations.AlterField(
            model_name='healthplan',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='ativo',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='numero',
            field=models.CharField(db_column='numero', max_length=30, verbose_name='número da carteirinha'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='numero',
            new_name='number',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='ativa',
            field=models.BooleanField(db_column='ativa', default=True, verbose_name='ativa'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='ativa',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='healthplan',
                    name='convenio_nome_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='healthplan',
                    constraint=models.UniqueConstraint(models.F('clinic'), django.db.models.functions.text.Lower('name'), name='convenio_nome_unico_por_clinica'),
                ),
                migrations.AlterModelOptions(
                    name='healthplan',
                    options={'ordering': ['name'], 'verbose_name': 'convênio', 'verbose_name_plural': 'convênios'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='membercard',
                    name='carteirinha_unica_por_convenio',
                ),
                migrations.AddConstraint(
                    model_name='membercard',
                    constraint=models.UniqueConstraint(fields=('clinic', 'convenio', 'number'), name='carteirinha_unica_por_convenio'),
                ),
                migrations.AlterModelOptions(
                    name='membercard',
                    options={'ordering': ['-active', 'convenio__name'], 'verbose_name': 'carteirinha', 'verbose_name_plural': 'carteirinhas'},
                ),
            ],
        ),
    ]
