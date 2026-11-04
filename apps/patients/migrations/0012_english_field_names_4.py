"""Field names in English (decision 164). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0009_english_field_names_3'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0020_english_field_names_3'),
        ('orcamentos', '0007_english_field_names_3'),
        ('pacientes', '0011_english_field_names_3'),
        ('pessoal', '0006_english_field_names_3'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0007_english_field_names_3'),
        ('rechamadas', '0005_english_field_names_3'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='tipo',
            field=models.CharField(choices=[('PF', 'Pessoa física'), ('PJ', 'Pessoa jurídica')], db_column='tipo', default='PF', max_length=2, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='tipo',
            new_name='kind',
        ),
    ]
