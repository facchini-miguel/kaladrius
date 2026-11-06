"""Field names in English (decision 164). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0009_english_field_names_3'),
        ('audit', '0004_english_field_names_2'),
        ('account', '0006_english_field_names_3'),
        ('health_plans', '0007_english_field_names_3'),
        ('core', '0022_english_field_names_3'),
        ('finance', '0020_english_field_names_3'),
        ('estimates', '0007_english_field_names_3'),
        ('patients', '0011_english_field_names_3'),
        ('staff', '0006_english_field_names_3'),
        ('practitioners', '0007_english_field_names_3'),
        ('medical_records', '0007_english_field_names_3'),
        ('recalls', '0005_english_field_names_3'),
        ('reference_data', '0006_english_field_names_3'),
    ]

    operations = [
        migrations.AlterField(
            model_name='addendum',
            name='atendimento',
            field=models.ForeignKey(db_column='atendimento_id', on_delete=django.db.models.deletion.PROTECT, related_name='adendos', to='medical_records.visit', verbose_name='atendimento'),
        ),
        migrations.RenameField(
            model_name='addendum',
            old_name='atendimento',
            new_name='visit',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='atendimento',
            field=models.ForeignKey(db_column='atendimento_id', on_delete=django.db.models.deletion.PROTECT, related_name='anexos', to='medical_records.visit', verbose_name='atendimento'),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='atendimento',
            new_name='visit',
        ),
        migrations.AlterField(
            model_name='attachment',
            name='tipo',
            field=models.CharField(db_column='tipo', max_length=50),
        ),
        migrations.RenameField(
            model_name='attachment',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='atendimento',
            field=models.ForeignKey(db_column='atendimento_id', on_delete=django.db.models.deletion.PROTECT, related_name='atestados', to='medical_records.visit', verbose_name='atendimento'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='atendimento',
            new_name='visit',
        ),
        migrations.AlterField(
            model_name='certificate',
            name='tipo',
            field=models.CharField(choices=[('comparecimento', 'Comparecimento'), ('afastamento', 'Afastamento')], db_column='tipo', default='comparecimento', max_length=20, verbose_name='tipo'),
        ),
        migrations.RenameField(
            model_name='certificate',
            old_name='tipo',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='examrequest',
            name='atendimento',
            field=models.ForeignKey(db_column='atendimento_id', on_delete=django.db.models.deletion.PROTECT, related_name='pedidos_de_exames', to='medical_records.visit', verbose_name='atendimento'),
        ),
        migrations.RenameField(
            model_name='examrequest',
            old_name='atendimento',
            new_name='visit',
        ),
        migrations.AlterField(
            model_name='prescription',
            name='atendimento',
            field=models.ForeignKey(db_column='atendimento_id', on_delete=django.db.models.deletion.PROTECT, related_name='receitas', to='medical_records.visit', verbose_name='atendimento'),
        ),
        migrations.RenameField(
            model_name='prescription',
            old_name='atendimento',
            new_name='visit',
        ),
        # The appointment's reverse accessor follows the model's name (`agendamento.visit`);
        # related_name lives in the state alone, no SQL.
        migrations.AlterField(
            model_name="visit",
            name="agendamento",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="visit",
                to="schedule.appointment",
                verbose_name="agendamento",
            ),
        ),
    ]
