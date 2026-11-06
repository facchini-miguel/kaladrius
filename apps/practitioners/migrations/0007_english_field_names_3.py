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
            model_name='practitioner',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='practitioner',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='ativo',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='practitioner',
                    name='profissional_clinica_nome',
                ),
                migrations.AddIndex(
                    model_name='practitioner',
                    index=models.Index(fields=['clinic', 'name'], name='profissional_clinica_nome'),
                ),
                migrations.AlterModelOptions(
                    name='practitioner',
                    options={'ordering': ['name'], 'verbose_name': 'profissional', 'verbose_name_plural': 'profissionais'},
                ),
            ],
        ),
    ]
