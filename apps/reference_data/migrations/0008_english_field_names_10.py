"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

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
            model_name='bank',
            name='nome_curto',
            field=models.CharField(db_column='nome_curto', max_length=100, verbose_name='nome curto'),
        ),
        migrations.RenameField(
            model_name='bank',
            old_name='nome_curto',
            new_name='short_name',
        ),
        migrations.AlterField(
            model_name='maritalstatus',
            name='ordem',
            field=models.PositiveSmallIntegerField(db_column='ordem', default=0, verbose_name='ordem'),
        ),
        migrations.RenameField(
            model_name='maritalstatus',
            old_name='ordem',
            new_name='sort_order',
        ),
        migrations.AlterField(
            model_name='state',
            name='sigla',
            field=models.CharField(db_column='sigla', max_length=2, unique=True, verbose_name='sigla'),
        ),
        migrations.RenameField(
            model_name='state',
            old_name='sigla',
            new_name='abbreviation',
        ),
        migrations.AlterField(
            model_name='state',
            name='regiao',
            field=models.CharField(db_column='regiao', max_length=20, verbose_name='região'),
        ),
        migrations.RenameField(
            model_name='state',
            old_name='regiao',
            new_name='region',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='maritalstatus',
                    options={'ordering': ['sort_order', 'name'], 'verbose_name': 'estado civil', 'verbose_name_plural': 'estados civis'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='state',
                    options={'ordering': ['abbreviation'], 'verbose_name': 'UF', 'verbose_name_plural': 'UFs'},
                ),
            ],
        ),
    ]
