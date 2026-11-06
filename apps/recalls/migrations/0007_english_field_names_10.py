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
            model_name='recall',
            name='concluida',
            field=models.BooleanField(db_column='concluida', default=False, verbose_name='concluída'),
        ),
        migrations.RenameField(
            model_name='recall',
            old_name='concluida',
            new_name='done',
        ),
    ]
