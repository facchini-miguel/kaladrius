"""Field names in English (decision 165). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0010_english_field_names_4'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('finance', '0021_english_field_names_4'),
        ('estimates', '0008_english_field_names_4'),
        ('patients', '0012_english_field_names_4'),
        ('staff', '0007_english_field_names_4'),
        ('practitioners', '0007_english_field_names_3'),
        ('medical_records', '0008_english_field_names_4'),
        ('recalls', '0005_english_field_names_3'),
        ('reference_data', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estimate',
            name='data',
            field=models.DateField(db_column='data', default=django.utils.timezone.localdate, verbose_name='data'),
        ),
        migrations.RenameField(
            model_name='estimate',
            old_name='data',
            new_name='date',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='estimate',
                    options={'ordering': ['-date', '-pk'], 'verbose_name': 'orçamento', 'verbose_name_plural': 'orçamentos'},
                ),
            ],
        ),
    ]
