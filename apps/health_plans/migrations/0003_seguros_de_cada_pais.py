from django.db import migrations, models


class Migration(migrations.Migration):
    """Each country's insurance (decision 125): the ANS registry becomes the insurer's registry
    in the clinic's country, kept as it was."""

    dependencies = [("health_plans", "0002_ordem_alfabetica")]

    operations = [
        migrations.RenameField("convenio", "registro_ans", "registro"),
        migrations.AlterField(
            model_name="convenio",
            name="registro",
            field=models.CharField(blank=True, max_length=20, verbose_name="registro da operadora"),
        ),
        migrations.AddField(
            model_name="carteirinha",
            name="grupo",
            field=models.CharField(blank=True, max_length=30, verbose_name="número do grupo"),
        ),
        migrations.AddField(
            model_name="carteirinha",
            name="beneficiario",
            field=models.CharField(
                blank=True, max_length=10, verbose_name="código do beneficiário"
            ),
        ),
    ]
