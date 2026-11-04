"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0007_english_field_names_1'),
        ('auditoria', '0003_english_field_names_1'),
        ('conta', '0003_english_model_names'),
        ('convenios', '0005_english_field_names_1'),
        ('core', '0020_english_field_names_1'),
        ('financeiro', '0018_english_field_names_1'),
        ('orcamentos', '0005_english_field_names_1'),
        ('pacientes', '0009_english_field_names_1'),
        ('pessoal', '0005_english_field_names_1'),
        ('profissionais', '0005_english_field_names_1'),
        ('prontuario', '0005_english_field_names_1'),
        ('rechamadas', '0003_english_field_names_1'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relatedperson',
            name='paciente',
            field=models.ForeignKey(db_column='paciente_id', on_delete=django.db.models.deletion.CASCADE, related_name='relacionados', to='pacientes.patient', verbose_name='paciente'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='paciente',
            new_name='patient',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_nao_e_o_proprio',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.CheckConstraint(condition=models.Q(('outro_paciente', models.F('patient')), _negated=True), name='relacionada_nao_e_o_proprio'),
                ),
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_unica',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.UniqueConstraint(fields=('patient', 'outro_paciente', 'vinculo'), name='relacionada_unica'),
                ),
            ],
        ),
    ]
