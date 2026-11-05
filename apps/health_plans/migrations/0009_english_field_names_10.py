"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
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
            model_name='membercard',
            name='convenio',
            field=models.ForeignKey(db_column='convenio_id', on_delete=django.db.models.deletion.PROTECT, related_name='carteirinhas', to='convenios.healthplan', verbose_name='convênio'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='convenio',
            new_name='health_plan',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='plano',
            field=models.CharField(blank=True, db_column='plano', max_length=100, verbose_name='plano'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='plano',
            new_name='plan',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='beneficiario',
            field=models.CharField(blank=True, db_column='beneficiario', max_length=10, verbose_name='código do beneficiário'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='beneficiario',
            new_name='member_code',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='titular',
            field=models.CharField(blank=True, db_column='titular', help_text='Se o paciente for dependente, o nome do titular do plano.', max_length=200, verbose_name='titular'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='titular',
            new_name='holder',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='membercard',
                    name='carteirinha_unica_por_convenio',
                ),
                migrations.AddConstraint(
                    model_name='membercard',
                    constraint=models.UniqueConstraint(fields=('clinic', 'health_plan', 'number'), name='carteirinha_unica_por_convenio'),
                ),
                migrations.AlterModelOptions(
                    name='membercard',
                    options={'ordering': ['-active', 'health_plan__name'], 'verbose_name': 'carteirinha', 'verbose_name_plural': 'carteirinhas'},
                ),
            ],
        ),
    ]
