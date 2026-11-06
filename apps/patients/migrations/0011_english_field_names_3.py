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
            model_name='patient',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', help_text='Para pessoa jurídica, o nome fantasia.', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='patient',
            name='numero',
            field=models.CharField(blank=True, db_column='numero', max_length=10, verbose_name='número'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='numero',
            new_name='number',
        ),
        migrations.AlterField(
            model_name='patient',
            name='observacoes',
            field=models.TextField(blank=True, db_column='observacoes', verbose_name='observações'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='observacoes',
            new_name='notes',
        ),
        migrations.AlterField(
            model_name='patient',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='ativo',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='relatedperson',
            name='nome',
            field=models.CharField(blank=True, db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='relatedperson',
            name='telefone',
            field=models.CharField(blank=True, db_column='telefone', max_length=11, verbose_name='telefone'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='telefone',
            new_name='phone',
        ),
        migrations.AlterField(
            model_name='relatedperson',
            name='observacao',
            field=models.CharField(blank=True, db_column='observacao', max_length=200, verbose_name='observação'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='observacao',
            new_name='note',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='patient',
                    name='paciente_clinica_nome',
                ),
                migrations.AddIndex(
                    model_name='patient',
                    index=models.Index(fields=['clinic', 'name'], name='paciente_clinica_nome'),
                ),
                migrations.AlterModelOptions(
                    name='patient',
                    options={'ordering': ['name'], 'verbose_name': 'paciente', 'verbose_name_plural': 'pacientes'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_paciente_ou_nome',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.CheckConstraint(condition=models.Q(('outro_paciente__isnull', False), models.Q(('name', ''), _negated=True), _connector='OR'), name='relacionada_paciente_ou_nome'),
                ),
            ],
        ),
    ]
