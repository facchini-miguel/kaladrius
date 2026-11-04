"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0010_english_field_names_4'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('financeiro', '0022_english_field_names_5'),
        ('orcamentos', '0009_english_field_names_5'),
        ('pacientes', '0012_english_field_names_4'),
        ('pessoal', '0007_english_field_names_4'),
        ('profissionais', '0007_english_field_names_3'),
        ('prontuario', '0009_english_field_names_5'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backup',
            name='momento',
            field=models.DateTimeField(auto_now_add=True, db_column='momento', db_index=True, verbose_name='quando'),
        ),
        migrations.RenameField(
            model_name='backup',
            old_name='momento',
            new_name='timestamp',
        ),
        migrations.AlterField(
            model_name='backup',
            name='arquivo',
            field=models.CharField(db_column='arquivo', max_length=200, verbose_name='arquivo'),
        ),
        migrations.RenameField(
            model_name='backup',
            old_name='arquivo',
            new_name='file',
        ),
        migrations.AlterField(
            model_name='backup',
            name='tamanho',
            field=models.PositiveBigIntegerField(db_column='tamanho', verbose_name='tamanho (bytes)'),
        ),
        migrations.RenameField(
            model_name='backup',
            old_name='tamanho',
            new_name='size',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='backup',
                    options={'ordering': ['-timestamp'], 'verbose_name': 'backup', 'verbose_name_plural': 'backups'},
                ),
            ],
        ),
    ]
