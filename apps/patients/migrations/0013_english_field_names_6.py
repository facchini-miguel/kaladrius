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
            model_name='patient',
            name='razao_social',
            field=models.CharField(blank=True, db_column='razao_social', max_length=200, verbose_name='razão social'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='razao_social',
            new_name='legal_name',
        ),
        migrations.AlterField(
            model_name='patient',
            name='cpf_cnpj',
            field=models.CharField(blank=True, db_column='cpf_cnpj', help_text='Pode ser digitado com ou sem pontuação.', max_length=20, verbose_name='documento'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='cpf_cnpj',
            new_name='tax_id',
        ),
        migrations.AlterField(
            model_name='patient',
            name='uf',
            field=models.ForeignKey(blank=True, db_column='uf_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='reference_data.state', verbose_name='UF'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='uf',
            new_name='state',
        ),
        migrations.AlterField(
            model_name='patient',
            name='cidade',
            field=models.ForeignKey(blank=True, db_column='cidade_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='reference_data.city', verbose_name='cidade'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='cidade',
            new_name='city',
        ),
        migrations.AlterField(
            model_name='patient',
            name='bairro',
            field=models.CharField(blank=True, db_column='bairro', max_length=100, verbose_name='bairro'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='bairro',
            new_name='neighborhood',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='patient',
                    name='paciente_clinica_cpf_cnpj',
                ),
                migrations.AddIndex(
                    model_name='patient',
                    index=models.Index(fields=['clinic', 'tax_id'], name='paciente_clinica_cpf_cnpj'),
                ),
                migrations.RemoveConstraint(
                    model_name='patient',
                    name='paciente_cpf_cnpj_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='patient',
                    constraint=models.UniqueConstraint(condition=models.Q(('tax_id', ''), _negated=True), fields=('clinic', 'tax_id'), name='paciente_cpf_cnpj_unico_por_clinica'),
                ),
            ],
        ),
    ]
