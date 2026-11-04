"""Field names in English (decision 163). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0008_english_field_names_2'),
        ('auditoria', '0004_english_field_names_2'),
        ('conta', '0005_remove_account_leftovers'),
        ('convenios', '0006_english_field_names_2'),
        ('core', '0021_english_field_names_2'),
        ('financeiro', '0019_english_field_names_2'),
        ('orcamentos', '0006_english_field_names_2'),
        ('pacientes', '0010_english_field_names_2'),
        ('pessoal', '0005_english_field_names_1'),
        ('profissionais', '0006_english_field_names_2'),
        ('prontuario', '0006_english_field_names_2'),
        ('rechamadas', '0004_english_field_names_2'),
        ('referencias', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='descricao',
            field=models.TextField(blank=True, db_column='descricao', verbose_name='descrição'),
        ),
        migrations.RenameField(
            model_name='appointment',
            old_name='descricao',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='appointmenttype',
            name='nome',
            field=models.CharField(db_collation='und-x-icu', db_column='nome', max_length=60, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='appointmenttype',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='appointmenttype',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='appointmenttype',
            old_name='ativo',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='appointmenttype',
                    name='tipo_atendimento_unico',
                ),
                migrations.AddConstraint(
                    model_name='appointmenttype',
                    constraint=models.UniqueConstraint(fields=('clinic', 'name'), name='tipo_atendimento_unico'),
                ),
                migrations.AlterModelOptions(
                    name='appointmenttype',
                    options={'ordering': ['name'], 'verbose_name': 'tipo de atendimento', 'verbose_name_plural': 'tipos de atendimento'},
                ),
            ],
        ),
    ]
