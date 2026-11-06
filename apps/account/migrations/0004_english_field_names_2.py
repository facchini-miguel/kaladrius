"""Field names in English (decision 161). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0007_english_field_names_1'),
        ('audit', '0003_english_field_names_1'),
        ('account', '0003_english_model_names'),
        ('health_plans', '0005_english_field_names_1'),
        ('core', '0020_english_field_names_1'),
        ('finance', '0018_english_field_names_1'),
        ('estimates', '0005_english_field_names_1'),
        ('patients', '0009_english_field_names_1'),
        ('staff', '0005_english_field_names_1'),
        ('practitioners', '0005_english_field_names_1'),
        ('medical_records', '0005_english_field_names_1'),
        ('recalls', '0003_english_field_names_1'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recoverycode',
            name='usuario',
            field=models.ForeignKey(db_column='usuario_id', on_delete=django.db.models.deletion.CASCADE, related_name='codigos_recuperacao', to=settings.AUTH_USER_MODEL, verbose_name='usuário'),
        ),
        migrations.RenameField(
            model_name='recoverycode',
            old_name='usuario',
            new_name='user',
        ),
        migrations.AlterField(
            model_name='twofactor',
            name='usuario',
            field=models.OneToOneField(db_column='usuario_id', on_delete=django.db.models.deletion.CASCADE, related_name='duas_etapas', to=settings.AUTH_USER_MODEL, verbose_name='usuário'),
        ),
        migrations.RenameField(
            model_name='twofactor',
            old_name='usuario',
            new_name='user',
        ),
    ]
