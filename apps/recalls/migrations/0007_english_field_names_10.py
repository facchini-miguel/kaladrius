"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0011_english_field_names_6'),
        ('auditoria', '0005_english_field_names_6'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0008_english_field_names_6'),
        ('core', '0024_english_field_names_9'),
        ('financeiro', '0024_english_field_names_7'),
        ('orcamentos', '0010_english_field_names_6'),
        ('pacientes', '0014_english_field_names_8'),
        ('pessoal', '0008_english_field_names_6'),
        ('profissionais', '0008_english_field_names_6'),
        ('prontuario', '0011_english_field_names_9'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0007_english_field_names_6'),
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
