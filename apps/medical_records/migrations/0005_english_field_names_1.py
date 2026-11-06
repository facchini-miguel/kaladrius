"""Field names in English (decision 160). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0006_english_model_names'),
        ('audit', '0002_english_model_names'),
        ('account', '0003_english_model_names'),
        ('health_plans', '0004_english_model_names'),
        ('core', '0019_english_model_names'),
        ('finance', '0017_english_model_names'),
        ('estimates', '0004_english_model_names'),
        ('patients', '0008_english_model_names'),
        ('staff', '0004_english_model_names'),
        ('practitioners', '0004_english_model_names'),
        ('medical_records', '0004_english_model_names'),
        ('recalls', '0002_english_model_names'),
        ('reference_data', '0005_english_model_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='addendum',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='addendum',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='addendum',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='visit',
            name='clinica',
            field=models.ForeignKey(db_column='clinica_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.clinic', verbose_name='clínica'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='clinica',
            new_name='clinic',
        ),
        migrations.AlterField(
            model_name='visit',
            name='criado_por',
            field=models.ForeignKey(db_column='criado_por_id', on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='criado_por',
            new_name='created_by',
        ),
        migrations.AlterField(
            model_name='visit',
            name='criado_em',
            field=models.DateTimeField(auto_now_add=True, db_column='criado_em'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='criado_em',
            new_name='created_at',
        ),
        migrations.AlterField(
            model_name='visit',
            name='alterado_em',
            field=models.DateTimeField(auto_now=True, db_column='alterado_em'),
        ),
        migrations.RenameField(
            model_name='visit',
            old_name='alterado_em',
            new_name='updated_at',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='addendum',
                    options={'ordering': ['created_at', 'pk'], 'verbose_name': 'adendo', 'verbose_name_plural': 'adendos'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='attachment',
                    options={'ordering': ['created_at', 'pk'], 'verbose_name': 'anexo', 'verbose_name_plural': 'anexos'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='certificate',
                    options={'ordering': ['created_at', 'pk'], 'verbose_name': 'atestado', 'verbose_name_plural': 'atestados'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='examrequest',
                    options={'ordering': ['created_at', 'pk'], 'verbose_name': 'pedido de exames', 'verbose_name_plural': 'pedidos de exames'},
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='prescription',
                    options={'ordering': ['created_at', 'pk'], 'verbose_name': 'receita', 'verbose_name_plural': 'receitas'},
                ),
            ],
        ),
    ]
