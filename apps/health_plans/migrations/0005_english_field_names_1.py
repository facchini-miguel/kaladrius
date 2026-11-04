"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0006_english_model_names'),
        ('auditoria', '0002_english_model_names'),
        ('conta', '0003_english_model_names'),
        ('convenios', '0004_english_model_names'),
        ('core', '0019_english_model_names'),
        ('financeiro', '0017_english_model_names'),
        ('orcamentos', '0004_english_model_names'),
        ('pacientes', '0008_english_model_names'),
        ('pessoal', '0004_english_model_names'),
        ('profissionais', '0004_english_model_names'),
        ('prontuario', '0004_english_model_names'),
        ('rechamadas', '0002_english_model_names'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='healthplan',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='healthplan',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='healthplan',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em', verbose_name='alterado em'),
        ),
        migrations.RenameField(
            model_name='healthplan',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='membercard',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em', verbose_name='alterado em'),
        ),
        migrations.RenameField(
            model_name='membercard',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='healthplan',
                    name='convenio_nome_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='healthplan',
                    constraint=models.UniqueConstraint(models.F('clinic'), django.db.models.functions.text.Lower('nome'), name='convenio_nome_unico_por_clinica'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='membercard',
                    name='carteirinha_unica_por_convenio',
                ),
                migrations.AddConstraint(
                    model_name='membercard',
                    constraint=models.UniqueConstraint(fields=('clinic', 'convenio', 'numero'), name='carteirinha_unica_por_convenio'),
                ),
            ],
        ),
    ]
