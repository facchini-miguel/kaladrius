"""Field names in English (decision 169). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import datetime
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
            model_name='clinic',
            name='documento',
            field=models.CharField(blank=True, db_column='documento', max_length=20, verbose_name='documento'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='documento',
            new_name='document',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='endereco',
            field=models.CharField(blank=True, db_column='endereco', help_text='Rua, número, bairro, cidade/UF e CEP, como sai no recibo.', max_length=250, verbose_name='endereço'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='endereco',
            new_name='address',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='moeda',
            field=models.CharField(choices=[('BRL', 'Real brasileiro (R$, BRL)'), ('USD', 'Dólar americano (US$, USD)'), ('EUR', 'Euro (€, EUR)'), ('GBP', 'Libra esterlina (£, GBP)'), ('CAD', 'Dólar canadense ($, CAD)'), ('AUD', 'Dólar australiano ($, AUD)'), ('ZAR', 'Rand sul-africano (R, ZAR)'), ('ARS', 'Peso argentino ($, ARS)'), ('MXN', 'Peso mexicano ($, MXN)'), ('CLP', 'Peso chileno ($, CLP)'), ('COP', 'Peso colombiano ($, COP)'), ('UYU', 'Peso uruguaio ($U, UYU)'), ('PYG', 'Guarani paraguaio (₲, PYG)'), ('PEN', 'Sol peruano (S/, PEN)'), ('BOB', 'Boliviano (Bs, BOB)')], db_column='moeda', default='BRL', help_text='Em que moeda a clínica trabalha. Muda só como os valores aparecem, para toda a equipe e em qualquer idioma: nenhum valor já lançado é convertido.', max_length=3, verbose_name='moeda'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='moeda',
            new_name='currency',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='pais',
            field=models.CharField(choices=[('BR', 'Brasil'), ('MX', 'México'), ('AR', 'Argentina'), ('CL', 'Chile'), ('CO', 'Colômbia'), ('PE', 'Peru'), ('UY', 'Uruguai'), ('PY', 'Paraguai'), ('BO', 'Bolívia'), ('EC', 'Equador'), ('US', 'Estados Unidos'), ('GB', 'Reino Unido'), ('CA', 'Canadá'), ('AU', 'Austrália'), ('ZA', 'África do Sul')], db_column='pais', default='BR', help_text='Define o fuso horário disponível, o formato de telefones, códigos postais e datas em inglês, e a moeda sugerida.', max_length=2, verbose_name='país'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='pais',
            new_name='country',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='fuso_horario',
            field=models.CharField(choices=[('Brasil', [('America/Sao_Paulo', 'Sao Paulo'), ('America/Manaus', 'Manaus'), ('America/Cuiaba', 'Cuiaba'), ('America/Campo_Grande', 'Campo Grande'), ('America/Porto_Velho', 'Porto Velho'), ('America/Boa_Vista', 'Boa Vista'), ('America/Rio_Branco', 'Rio Branco'), ('America/Noronha', 'Noronha')]), ('México', [('America/Mexico_City', 'Mexico City'), ('America/Cancun', 'Cancun'), ('America/Chihuahua', 'Chihuahua'), ('America/Hermosillo', 'Hermosillo'), ('America/Mazatlan', 'Mazatlan'), ('America/Tijuana', 'Tijuana')]), ('Argentina', [('America/Argentina/Buenos_Aires', 'Buenos Aires'), ('America/Argentina/Cordoba', 'Cordoba'), ('America/Argentina/Mendoza', 'Mendoza')]), ('Chile', [('America/Santiago', 'Santiago'), ('America/Punta_Arenas', 'Punta Arenas'), ('Pacific/Easter', 'Easter')]), ('Colômbia', [('America/Bogota', 'Bogota')]), ('Peru', [('America/Lima', 'Lima')]), ('Uruguai', [('America/Montevideo', 'Montevideo')]), ('Paraguai', [('America/Asuncion', 'Asuncion')]), ('Bolívia', [('America/La_Paz', 'La Paz')]), ('Equador', [('America/Guayaquil', 'Guayaquil'), ('Pacific/Galapagos', 'Galapagos')]), ('Estados Unidos', [('America/New_York', 'New York'), ('America/Chicago', 'Chicago'), ('America/Denver', 'Denver'), ('America/Phoenix', 'Phoenix'), ('America/Los_Angeles', 'Los Angeles'), ('America/Anchorage', 'Anchorage'), ('Pacific/Honolulu', 'Honolulu')]), ('Reino Unido', [('Europe/London', 'London')]), ('Canadá', [('America/Toronto', 'Toronto'), ('America/Vancouver', 'Vancouver'), ('America/Edmonton', 'Edmonton'), ('America/Winnipeg', 'Winnipeg'), ('America/Regina', 'Regina'), ('America/Halifax', 'Halifax'), ('America/St_Johns', 'St Johns')]), ('Austrália', [('Australia/Sydney', 'Sydney'), ('Australia/Melbourne', 'Melbourne'), ('Australia/Brisbane', 'Brisbane'), ('Australia/Adelaide', 'Adelaide'), ('Australia/Darwin', 'Darwin'), ('Australia/Perth', 'Perth'), ('Australia/Hobart', 'Hobart')]), ('África do Sul', [('Africa/Johannesburg', 'Johannesburg')])], db_column='fuso_horario', default='America/Sao_Paulo', help_text='Os horários da agenda e de todo o sistema seguem este fuso.', max_length=40, verbose_name='fuso horário'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='fuso_horario',
            new_name='time_zone',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='numeracao_dentaria',
            field=models.CharField(choices=[('fdi', 'FDI (11 a 48; dentes de leite 51 a 85)'), ('universal', 'Universal, dos Estados Unidos (1 a 32; dentes de leite A a T)'), ('palmer', 'Palmer (UR6, LL3; dentes de leite URE a LRE)')], db_column='numeracao_dentaria', default='fdi', help_text='Como os dentes aparecem no odontograma e nos orçamentos. Muda só a exibição: os dentes já registrados continuam os mesmos.', max_length=10, verbose_name='numeração dos dentes'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='numeracao_dentaria',
            new_name='tooth_numbering',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='exigir_duas_etapas',
            field=models.BooleanField(db_column='exigir_duas_etapas', default=False, help_text='Profissionais com prontuário, administradores e o financeiro só usam o sistema depois de ativar o código do aplicativo autenticador. A recepção não é obrigada.', verbose_name='exigir verificação em duas etapas de quem acessa o prontuário ou o financeiro'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='exigir_duas_etapas',
            new_name='require_two_factor',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='agenda_inicio',
            field=models.TimeField(db_column='agenda_inicio', default=datetime.time(7, 30), verbose_name='início da agenda'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='agenda_inicio',
            new_name='schedule_start',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='agenda_fim',
            field=models.TimeField(db_column='agenda_fim', default=datetime.time(20, 0), verbose_name='fim da agenda'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='agenda_fim',
            new_name='schedule_end',
        ),
        migrations.AlterField(
            model_name='clinic',
            name='agenda_intervalo',
            field=models.PositiveSmallIntegerField(choices=[(10, '10 minutos'), (15, '15 minutos'), (20, '20 minutos'), (30, '30 minutos'), (60, '1 hora')], db_column='agenda_intervalo', default=30, verbose_name='duração de cada horário'),
        ),
        migrations.RenameField(
            model_name='clinic',
            old_name='agenda_intervalo',
            new_name='schedule_interval',
        ),
        migrations.AlterField(
            model_name='membership',
            name='papel',
            field=models.CharField(choices=[('admin', 'Administrador da clínica'), ('recepcao', 'Recepção'), ('profissional', 'Profissional'), ('financeiro', 'Financeiro')], db_column='papel', max_length=20, verbose_name='perfil'),
        ),
        migrations.RenameField(
            model_name='membership',
            old_name='papel',
            new_name='role',
        ),
        migrations.AlterField(
            model_name='user',
            name='idioma',
            field=models.CharField(blank=True, choices=[('pt-br', 'Português'), ('en', 'English'), ('es', 'Español')], db_column='idioma', help_text='Vazio: o idioma do navegador.', max_length=10, verbose_name='idioma'),
        ),
        migrations.RenameField(
            model_name='user',
            old_name='idioma',
            new_name='language',
        ),
        migrations.AlterField(
            model_name='user',
            name='ultima_versao_vista',
            field=models.CharField(blank=True, db_column='ultima_versao_vista', editable=False, max_length=20, verbose_name='última versão vista nas novidades'),
        ),
        migrations.RenameField(
            model_name='user',
            old_name='ultima_versao_vista',
            new_name='last_seen_version',
        ),
        migrations.AlterField(
            model_name='user',
            name='demonstracao',
            field=models.BooleanField(db_column='demonstracao', default=False, editable=False, verbose_name='conta de demonstração'),
        ),
        migrations.RenameField(
            model_name='user',
            old_name='demonstracao',
            new_name='demo',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='clinic',
                    name='clinica_agenda_inicio_antes_do_fim',
                ),
                migrations.AddConstraint(
                    model_name='clinic',
                    constraint=models.CheckConstraint(condition=models.Q(('schedule_start__lt', models.F('schedule_end'))), name='clinica_agenda_inicio_antes_do_fim', violation_error_message='O início da agenda deve ser antes do fim.'),
                ),
            ],
        ),
    ]
