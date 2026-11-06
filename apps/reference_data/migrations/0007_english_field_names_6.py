"""Field names in English (decision 166). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0010_english_field_names_4'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('finance', '0022_english_field_names_5'),
        ('estimates', '0009_english_field_names_5'),
        ('patients', '0012_english_field_names_4'),
        ('staff', '0007_english_field_names_4'),
        ('practitioners', '0007_english_field_names_3'),
        ('medical_records', '0009_english_field_names_5'),
        ('recalls', '0006_english_field_names_5'),
        ('reference_data', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='city',
            name='uf',
            field=models.ForeignKey(db_column='uf_id', on_delete=django.db.models.deletion.PROTECT, related_name='cidades', to='reference_data.state', verbose_name='UF'),
        ),
        migrations.RenameField(
            model_name='city',
            old_name='uf',
            new_name='state',
        ),
        migrations.AlterField(
            model_name='neighborhood',
            name='cidade',
            field=models.ForeignKey(db_column='cidade_id', on_delete=django.db.models.deletion.CASCADE, related_name='bairros', to='reference_data.city', verbose_name='cidade'),
        ),
        migrations.RenameField(
            model_name='neighborhood',
            old_name='cidade',
            new_name='city',
        ),
        migrations.AlterField(
            model_name='street',
            name='cidade',
            field=models.ForeignKey(db_column='cidade_id', on_delete=django.db.models.deletion.CASCADE, related_name='logradouros', to='reference_data.city', verbose_name='cidade'),
        ),
        migrations.RenameField(
            model_name='street',
            old_name='cidade',
            new_name='city',
        ),
        migrations.AlterField(
            model_name='street',
            name='bairro',
            field=models.ForeignKey(blank=True, db_column='bairro_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logradouros', to='reference_data.neighborhood', verbose_name='bairro'),
        ),
        migrations.RenameField(
            model_name='street',
            old_name='bairro',
            new_name='neighborhood',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='city',
                    name='cidade_uf_nome',
                ),
                migrations.AddIndex(
                    model_name='city',
                    index=models.Index(fields=['state', 'name'], name='cidade_uf_nome'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='neighborhood',
                    name='bairro_unico_por_cidade',
                ),
                migrations.AddConstraint(
                    model_name='neighborhood',
                    constraint=models.UniqueConstraint(fields=('city', 'name'), name='bairro_unico_por_cidade'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='street',
                    name='logradouro_unico_por_bairro',
                ),
                migrations.AddConstraint(
                    model_name='street',
                    constraint=models.UniqueConstraint(fields=('city', 'neighborhood', 'name'), name='logradouro_unico_por_bairro'),
                ),
            ],
        ),
    ]
