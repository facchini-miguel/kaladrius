"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.core.validators
from decimal import Decimal
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
            model_name='practitioner',
            name='comissao_percentual',
            field=models.DecimalField(db_column='comissao_percentual', decimal_places=2, default=Decimal('0'), help_text='Percentual sobre o valor recebido dos lançamentos deste profissional.', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0')), django.core.validators.MaxValueValidator(Decimal('100'))], verbose_name='comissão (%)'),
        ),
        migrations.RenameField(
            model_name='practitioner',
            old_name='comissao_percentual',
            new_name='commission_percentage',
        ),
    ]
