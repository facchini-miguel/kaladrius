"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

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
            model_name='recoverycode',
            name='resumo',
            field=models.CharField(db_column='resumo', editable=False, max_length=64),
        ),
        migrations.RenameField(
            model_name='recoverycode',
            old_name='resumo',
            new_name='digest',
        ),
        migrations.AlterField(
            model_name='recoverycode',
            name='usado_em',
            field=models.DateTimeField(blank=True, db_column='usado_em', null=True, verbose_name='usado em'),
        ),
        migrations.RenameField(
            model_name='recoverycode',
            old_name='usado_em',
            new_name='used_at',
        ),
        migrations.AlterField(
            model_name='twofactor',
            name='segredo',
            field=models.CharField(db_column='segredo', editable=False, max_length=64, verbose_name='segredo'),
        ),
        migrations.RenameField(
            model_name='twofactor',
            old_name='segredo',
            new_name='secret',
        ),
        migrations.AlterField(
            model_name='twofactor',
            name='ativada_em',
            field=models.DateTimeField(blank=True, db_column='ativada_em', null=True, verbose_name='ativada em'),
        ),
        migrations.RenameField(
            model_name='twofactor',
            old_name='ativada_em',
            new_name='activated_at',
        ),
        migrations.AlterField(
            model_name='twofactor',
            name='ultimo_passo',
            field=models.BigIntegerField(db_column='ultimo_passo', default=0, editable=False),
        ),
        migrations.RenameField(
            model_name='twofactor',
            old_name='ultimo_passo',
            new_name='last_step',
        ),
        # Labels the English names would otherwise give (decision 170): state only, no SQL.
        migrations.AlterField(
            model_name="recoverycode",
            name="digest",
            field=models.CharField(
                db_column="resumo", editable=False, max_length=64, verbose_name="resumo"
            ),
        ),
        migrations.AlterField(
            model_name="twofactor",
            name="last_step",
            field=models.BigIntegerField(
                db_column="ultimo_passo", default=0, editable=False, verbose_name="último passo"
            ),
        ),
    ]
