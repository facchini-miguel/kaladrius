"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
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
            model_name='practitioner',
            name='usuario',
            field=models.ForeignKey(blank=True, db_column='usuario_id', help_text='Conta usada por este profissional para entrar no sistema (opcional).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profissionais', to=settings.AUTH_USER_MODEL, verbose_name='usuário de acesso'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='usuario',
            new_name='user',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='practitioner',
                    name='profissional_usuario_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='practitioner',
                    constraint=models.UniqueConstraint(condition=models.Q(('user__isnull', False)), fields=('clinic', 'user'), name='profissional_usuario_unico_por_clinica'),
                ),
            ],
        ),
    ]
