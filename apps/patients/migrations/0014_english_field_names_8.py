"""Field names in English (decision 168). Each field keeps its column (db_column), so
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
        ('pacientes', '0013_english_field_names_6'),
        ('pessoal', '0008_english_field_names_6'),
        ('profissionais', '0008_english_field_names_6'),
        ('prontuario', '0010_english_field_names_6'),
        ('rechamadas', '0006_english_field_names_5'),
        ('referencias', '0007_english_field_names_6'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='inscricao_estadual',
            field=models.CharField(blank=True, db_column='inscricao_estadual', max_length=20, verbose_name='inscrição estadual'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='inscricao_estadual',
            new_name='state_registration',
        ),
        migrations.AlterField(
            model_name='patient',
            name='sexo',
            field=models.CharField(blank=True, choices=[('F', 'Feminino'), ('M', 'Masculino'), ('O', 'Outro')], db_column='sexo', max_length=1, verbose_name='sexo'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='sexo',
            new_name='sex',
        ),
        migrations.AlterField(
            model_name='patient',
            name='data_nascimento',
            field=models.DateField(blank=True, db_column='data_nascimento', null=True, verbose_name='data de nascimento'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='data_nascimento',
            new_name='birth_date',
        ),
        migrations.AlterField(
            model_name='patient',
            name='estado_civil',
            field=models.ForeignKey(blank=True, db_column='estado_civil_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='referencias.maritalstatus', verbose_name='estado civil'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='estado_civil',
            new_name='marital_status',
        ),
        migrations.AlterField(
            model_name='patient',
            name='profissao',
            field=models.CharField(blank=True, db_column='profissao', max_length=100, verbose_name='profissão'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='profissao',
            new_name='occupation',
        ),
        migrations.AlterField(
            model_name='patient',
            name='responsavel',
            field=models.CharField(blank=True, db_column='responsavel', help_text='Para menores de idade, por exemplo.', max_length=200, verbose_name='responsável'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='responsavel',
            new_name='guardian',
        ),
        migrations.AlterField(
            model_name='patient',
            name='telefone_celular',
            field=models.CharField(blank=True, db_column='telefone_celular', max_length=11, verbose_name='celular'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='telefone_celular',
            new_name='mobile_phone',
        ),
        migrations.AlterField(
            model_name='patient',
            name='telefone_residencial',
            field=models.CharField(blank=True, db_column='telefone_residencial', max_length=11, verbose_name='telefone residencial'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='telefone_residencial',
            new_name='home_phone',
        ),
        migrations.AlterField(
            model_name='patient',
            name='telefone_comercial',
            field=models.CharField(blank=True, db_column='telefone_comercial', max_length=11, verbose_name='telefone comercial'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='telefone_comercial',
            new_name='work_phone',
        ),
        migrations.AlterField(
            model_name='patient',
            name='cep',
            field=models.CharField(blank=True, db_column='cep', max_length=9, verbose_name='CEP'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='cep',
            new_name='postal_code',
        ),
        migrations.AlterField(
            model_name='patient',
            name='estado_nome',
            field=models.CharField(blank=True, db_column='estado_nome', max_length=60, verbose_name='estado ou província'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='estado_nome',
            new_name='state_name',
        ),
        migrations.AlterField(
            model_name='patient',
            name='cidade_nome',
            field=models.CharField(blank=True, db_column='cidade_nome', max_length=100, verbose_name='cidade'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='cidade_nome',
            new_name='city_name',
        ),
        migrations.AlterField(
            model_name='patient',
            name='logradouro',
            field=models.CharField(blank=True, db_column='logradouro', help_text='Rua, avenida…', max_length=200, verbose_name='endereço'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='logradouro',
            new_name='street',
        ),
        migrations.AlterField(
            model_name='patient',
            name='complemento',
            field=models.CharField(blank=True, db_column='complemento', max_length=100, verbose_name='complemento'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='complemento',
            new_name='complement',
        ),
        migrations.AlterField(
            model_name='patient',
            name='arquivado',
            field=models.BooleanField(db_column='arquivado', default=False, verbose_name='arquivado'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='arquivado',
            new_name='archived',
        ),
        migrations.AlterField(
            model_name='patient',
            name='arquivado_em',
            field=models.DateTimeField(blank=True, db_column='arquivado_em', null=True, verbose_name='arquivado em'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='arquivado_em',
            new_name='archived_at',
        ),
        migrations.AlterField(
            model_name='patient',
            name='arquivado_por',
            field=models.ForeignKey(blank=True, db_column='arquivado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='arquivado por'),
        ),
        migrations.RenameField(
            model_name='patient',
            old_name='arquivado_por',
            new_name='archived_by',
        ),
        migrations.AlterField(
            model_name='relatedperson',
            name='vinculo',
            field=models.CharField(choices=[('mae', 'Mãe'), ('pai', 'Pai'), ('responsavel', 'Responsável legal'), ('conjuge', 'Cônjuge'), ('filho', 'Filho(a)'), ('irmao', 'Irmão(ã)'), ('avo', 'Avô/avó'), ('neto', 'Neto(a)'), ('parente', 'Outro parente'), ('emergencia', 'Contato de emergência'), ('contato', 'Contato')], db_column='vinculo', max_length=20, verbose_name='vínculo'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='vinculo',
            new_name='relationship',
        ),
        migrations.AlterField(
            model_name='relatedperson',
            name='outro_paciente',
            field=models.ForeignKey(blank=True, db_column='outro_paciente_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='relacionado_a', to='pacientes.patient', verbose_name='paciente da clínica'),
        ),
        migrations.RenameField(
            model_name='relatedperson',
            old_name='outro_paciente',
            new_name='other_patient',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_paciente_ou_nome',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.CheckConstraint(condition=models.Q(('other_patient__isnull', False), models.Q(('name', ''), _negated=True), _connector='OR'), name='relacionada_paciente_ou_nome'),
                ),
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_nao_e_o_proprio',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.CheckConstraint(condition=models.Q(('other_patient', models.F('patient')), _negated=True), name='relacionada_nao_e_o_proprio'),
                ),
                migrations.RemoveConstraint(
                    model_name='relatedperson',
                    name='relacionada_unica',
                ),
                migrations.AddConstraint(
                    model_name='relatedperson',
                    constraint=models.UniqueConstraint(fields=('patient', 'other_patient', 'relationship'), name='relacionada_unica'),
                ),
            ],
        ),
    ]
