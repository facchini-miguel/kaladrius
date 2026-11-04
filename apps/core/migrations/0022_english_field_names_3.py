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
            model_name='clinic',
            name='nome',
            field=models.CharField(db_column='nome', max_length=200, verbose_name='nome'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='nome',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='telefone',
            field=models.CharField(blank=True, db_column='telefone', max_length=20, verbose_name='telefone'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='telefone',
            new_name='phone',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='ativa',
            field=models.BooleanField(db_column='ativa', default=True, verbose_name='ativa'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='ativa',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='clinicmodule',
            name='codigo',
            field=models.CharField(choices=[('odontologia', 'Odontologia'), ('medicina', 'Medicina'), ('agenda', 'Agenda'), ('prontuario', 'Prontuário'), ('orcamentos', 'Orçamentos'), ('financeiro', 'Financeiro'), ('rechamadas', 'Rechamadas'), ('aniversariantes', 'Aniversariantes'), ('convenios', 'Convênios'), ('pessoal', 'Pessoal')], db_column='codigo', max_length=20, verbose_name='módulo'),
        ),
        migrations.RenameField(
            model_name='clinicmodule',
            old_name='codigo',
            new_name='code',
        ),
        migrations.AlterField(
            model_name='clinicmodule',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='clinicmodule',
            old_name='ativo',
            new_name='active',
        ),
        migrations.AlterField(
            model_name='membership',
            name='ativo',
            field=models.BooleanField(db_column='ativo', default=True, verbose_name='ativo'),
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='ativo',
            new_name='active',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='clinic',
                    options={'ordering': ['name'], 'verbose_name': 'clínica', 'verbose_name_plural': 'clínicas'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='clinicmodule',
                    name='modulo_unico_por_clinica',
                ),
                migrations.AddConstraint(
                    model_name='clinicmodule',
                    constraint=models.UniqueConstraint(fields=('clinic', 'code'), name='modulo_unico_por_clinica'),
                ),
                migrations.RemoveConstraint(
                    model_name='clinicmodule',
                    name='modulo_clinico_conhecido',
                ),
                migrations.AddConstraint(
                    model_name='clinicmodule',
                    constraint=models.CheckConstraint(condition=models.Q(('code__in', ['odontologia', 'medicina', 'agenda', 'prontuario', 'orcamentos', 'financeiro', 'rechamadas', 'aniversariantes', 'convenios', 'pessoal'])), name='modulo_clinico_conhecido'),
                ),
                migrations.AlterModelOptions(
                    name='clinicmodule',
                    options={'ordering': ['code'], 'verbose_name': 'módulo da clínica', 'verbose_name_plural': 'módulos da clínica'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='membership',
                    options={'ordering': ['clinic__name', 'user__username'], 'verbose_name': 'vínculo com clínica', 'verbose_name_plural': 'vínculos com clínicas'},
                ),
            ],
        ),
    ]
