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
            model_name='attachment',
            name='descricao',
            field=models.CharField(blank=True, db_column='descricao', help_text='Por exemplo: hemograma de março.', max_length=200, verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='descricao',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='nome',
            field=models.CharField(db_column='nome', max_length=255, verbose_name='arquivo'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='observacao',
            field=models.TextField(blank=True, db_column='observacao', help_text='Aparece no atestado. Por exemplo: deve permanecer em repouso.', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='observacao',
            new_name='note',
        ),
    ]
