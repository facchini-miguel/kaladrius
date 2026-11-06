"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0011_english_field_names_6'),
        ('audit', '0005_english_field_names_6'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0008_english_field_names_6'),
        ('core', '0024_english_field_names_9'),
        ('finance', '0024_english_field_names_7'),
        ('estimates', '0010_english_field_names_6'),
        ('patients', '0014_english_field_names_8'),
        ('staff', '0008_english_field_names_6'),
        ('practitioners', '0008_english_field_names_6'),
        ('medical_records', '0011_english_field_names_9'),
        ('recalls', '0006_english_field_names_5'),
        ('reference_data', '0007_english_field_names_6'),
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
