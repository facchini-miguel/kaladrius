"""Field names in English (decision 169). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0011_english_field_names_6'),
        ('auditoria', '0005_english_field_names_6'),
        ('conta', '0006_english_field_names_3'),
        ('convenios', '0008_english_field_names_6'),
        ('core', '0023_english_field_names_6'),
        ('financeiro', '0024_english_field_names_7'),
        ('orcamentos', '0010_english_field_names_6'),
        ('pacientes', '0014_english_field_names_8'),
        ('pessoal', '0008_english_field_names_6'),
        ('profissionais', '0008_english_field_names_6'),
        ('prontuario', '0010_english_field_names_6'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0007_english_field_names_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='addendum',
            name='texto',
            field=models.TextField(db_column='texto', verbose_name='adendo'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='texto',
            new_name='text',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='conteudo',
            field=models.BinaryField(db_column='conteudo'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='conteudo',
            new_name='content',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='hora_inicio',
            field=models.TimeField(blank=True, db_column='hora_inicio', null=True, verbose_name='das'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='hora_inicio',
            new_name='start_time',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='hora_fim',
            field=models.TimeField(blank=True, db_column='hora_fim', null=True, verbose_name='às'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='hora_fim',
            new_name='end_time',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='dias',
            field=models.PositiveSmallIntegerField(blank=True, db_column='dias', help_text='Só para afastamento.', null=True, verbose_name='dias de afastamento'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='dias',
            new_name='days',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='exames',
            field=models.TextField(db_column='exames', help_text='Um exame por linha.', verbose_name='exames'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='exames',
            new_name='exams',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='indicacao',
            field=models.TextField(blank=True, db_column='indicacao', help_text='Aparece no pedido.', verbose_name='indicação clínica'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='indicacao',
            new_name='indication',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='prescricao',
            field=models.TextField(db_column='prescricao', help_text='Um item por linha: medicamento, dose e como usar.', verbose_name='medicamentos e como usar'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='prescricao',
            new_name='medications',
        ),
        migrations.AlterField(
            model_name='visit',
            name='agendamento',
            field=models.OneToOneField(blank=True, db_column='agendamento_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visit', to='agenda.appointment', verbose_name='agendamento'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='agendamento',
            new_name='appointment',
        ),
        migrations.AlterField(
            model_name='visit',
            name='queixa_principal',
            field=models.TextField(blank=True, db_column='queixa_principal', verbose_name='queixa principal'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='queixa_principal',
            new_name='chief_complaint',
        ),
        migrations.AlterField(
            model_name='visit',
            name='historia',
            field=models.TextField(blank=True, db_column='historia', verbose_name='história da doença atual'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='historia',
            new_name='present_illness',
        ),
        migrations.AlterField(
            model_name='visit',
            name='antecedentes',
            field=models.TextField(blank=True, db_column='antecedentes', help_text='Pessoais e familiares, medicamentos em uso, alergias.', verbose_name='antecedentes'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='antecedentes',
            new_name='medical_history',
        ),
        migrations.AlterField(
            model_name='visit',
            name='exame_fisico',
            field=models.TextField(blank=True, db_column='exame_fisico', verbose_name='exame físico'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='exame_fisico',
            new_name='physical_exam',
        ),
        migrations.AlterField(
            model_name='visit',
            name='conduta',
            field=models.TextField(blank=True, db_column='conduta', verbose_name='conduta e plano'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='conduta',
            new_name='plan',
        ),
        migrations.AlterField(
            model_name='visit',
            name='finalizado_em',
            field=models.DateTimeField(blank=True, db_column='finalizado_em', null=True, verbose_name='finalizado em'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='finalizado_em',
            new_name='finalized_at',
        ),
        migrations.AlterField(
            model_name='visit',
            name='finalizado_por',
            field=models.ForeignKey(blank=True, db_column='finalizado_por_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='finalizado_por',
            new_name='finalized_by',
        ),
    ]
