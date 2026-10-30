import django.db.models.deletion
from django.db import migrations, models


def habilitar_areas_existentes(apps, schema_editor):
    Clinica = apps.get_model("core", "Clinica")
    Modulo = apps.get_model("core", "ModuloDaClinica")
    alias = schema_editor.connection.alias
    for clinica in Clinica.objects.using(alias).all().iterator():
        Modulo.objects.using(alias).bulk_create(
            [
                Modulo(clinica_id=clinica.pk, codigo=codigo, ativo=clinica.area == codigo)
                for codigo in ("odontologia", "medicina")
            ]
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0009_papel_financeiro")]

    operations = [
        migrations.CreateModel(
            name="ModuloDaClinica",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "codigo",
                    models.CharField(
                        choices=[("odontologia", "Odontologia"), ("medicina", "Medicina")],
                        max_length=20,
                        verbose_name="módulo",
                    ),
                ),
                ("ativo", models.BooleanField(default=True, verbose_name="ativo")),
                (
                    "clinica",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.clinica",
                        verbose_name="clínica",
                    ),
                ),
            ],
            options={
                "verbose_name": "módulo da clínica",
                "verbose_name_plural": "módulos da clínica",
                "ordering": ["codigo"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("clinica", "codigo"), name="modulo_unico_por_clinica"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(codigo__in=["odontologia", "medicina"]),
                        name="modulo_clinico_conhecido",
                    ),
                ],
            },
        ),
        migrations.RunPython(habilitar_areas_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="clinica",
            name="area",
            field=models.CharField(
                choices=[
                    ("odontologia", "Odontologia"),
                    ("medicina", "Medicina"),
                    ("outra", "Outra área da saúde"),
                ],
                default="odontologia",
                help_text=(
                    "Define os tipos iniciais de atendimento. Os módulos clínicos são escolhidos "
                    "separadamente e podem ser usados juntos."
                ),
                max_length=20,
                verbose_name="área principal",
            ),
        ),
    ]
