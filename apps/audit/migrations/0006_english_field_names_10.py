"""Field names in English (decision 171). Each field keeps its column (db_column), so
no SQL runs: an app rolled back to an older version still finds them."""

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
            model_name='auditentry',
            name='usuario_nome',
            field=models.CharField(blank=True, db_column='usuario_nome', max_length=150, verbose_name='usuário (texto)'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='usuario_nome',
            new_name='user_name',
        ),
        migrations.AlterField(
            model_name='auditentry',
            name='acao',
            field=models.CharField(choices=[('criar', 'Criou'), ('alterar', 'Alterou'), ('excluir', 'Excluiu'), ('visualizar', 'Visualizou'), ('login', 'Entrou no sistema'), ('login_falhou', 'Tentativa de entrada recusada'), ('logout', 'Saiu do sistema')], db_column='acao', max_length=20, verbose_name='ação'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='acao',
            new_name='action',
        ),
        migrations.AlterField(
            model_name='auditentry',
            name='modelo',
            field=models.CharField(blank=True, db_column='modelo', max_length=50, verbose_name='tipo de registro'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='modelo',
            new_name='model_name',
        ),
        migrations.AlterField(
            model_name='auditentry',
            name='objeto_id',
            field=models.CharField(blank=True, db_column='objeto_id', max_length=40, verbose_name='código do registro'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='objeto_id',
            new_name='object_id',
        ),
        migrations.AlterField(
            model_name='auditentry',
            name='objeto_descricao',
            field=models.CharField(blank=True, db_column='objeto_descricao', max_length=200, verbose_name='registro'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='objeto_descricao',
            new_name='object_repr',
        ),
        migrations.AlterField(
            model_name='auditentry',
            name='alteracoes',
            field=models.JSONField(blank=True, db_column='alteracoes', default=dict, verbose_name='alterações'),
        ),
        migrations.RenameField(
            model_name='auditentry',
            old_name='alteracoes',
            new_name='changes',
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name='auditentry',
                    name='auditoria_objeto',
                ),
                migrations.AddIndex(
                    model_name='auditentry',
                    index=models.Index(fields=['model_name', 'object_id'], name='auditoria_objeto'),
                ),
            ],
        ),
    ]
