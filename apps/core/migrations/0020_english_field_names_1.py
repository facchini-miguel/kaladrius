"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
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
            model_name='clinic',
            name='criada_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criada_em', verbose_name='criada em'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='criada_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='alterada_em',
            field=models.DateTimeField(auto_now=True, db_column='alterada_em', verbose_name='alterada em'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='alterada_em',
            new_name='updated_at',
        ),
        migrations.AlterField(
            model_name='clinicmodule',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='clinicmodule',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='membership',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.CASCADE, related_name='vinculos', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='membership',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em', verbose_name='criado em'),
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='clinicmodule',
                    name='modulo_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='clinicmodule',
                    constraint=models.UniqueConstraint(fields=('clinic', 'codigo'), name='modulo_unico_por_clinica'),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='membership',
                    name='vinculo_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='membership',
                    constraint=models.UniqueConstraint(fields=('usuario', 'clinic'), name='vinculo_unico_por_clinica', violation_error_message='Este usuário já está vinculado a esta clínica.'),
                ),
                migrations.AlterModelOptions(
                    name='membership',
                    options={'ordering': ['clinic__nome', 'usuario__username'], 'verbose_name': 'vínculo com clínica', 'verbose_name_plural': 'vínculos com clínicas'},
                ),
            ],
        ),
    ]
