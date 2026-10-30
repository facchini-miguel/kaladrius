from django.db import migrations, models

GERAIS = (
    "agenda",
    "prontuario",
    "orcamentos",
    "financeiro",
    "rechamadas",
    "aniversariantes",
    "convenios",
)
CODIGOS = ("odontologia", "medicina", *GERAIS)


def ligar_modulos_gerais(apps, schema_editor):
    """Existing clinics keep everything they had: every general module starts on."""
    Clinica = apps.get_model("core", "Clinica")
    Modulo = apps.get_model("core", "ModuloDaClinica")
    alias = schema_editor.connection.alias
    for clinica_id in Clinica.objects.using(alias).values_list("pk", flat=True).iterator():
        existentes = set(
            Modulo.objects.using(alias)
            .filter(clinica_id=clinica_id)
            .values_list("codigo", flat=True)
        )
        Modulo.objects.using(alias).bulk_create(
            [
                Modulo(clinica_id=clinica_id, codigo=codigo, ativo=True)
                for codigo in GERAIS
                if codigo not in existentes
            ]
        )


def remover_modulos_gerais(apps, schema_editor):
    Modulo = apps.get_model("core", "ModuloDaClinica")
    Modulo.objects.using(schema_editor.connection.alias).filter(codigo__in=GERAIS).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0010_modulos_clinicos")]

    operations = [
        migrations.RemoveConstraint(model_name="modulodaclinica", name="modulo_clinico_conhecido"),
        migrations.AlterField(
            model_name="modulodaclinica",
            name="codigo",
            field=models.CharField(
                choices=[
                    ("odontologia", "Odontologia"),
                    ("medicina", "Medicina"),
                    ("agenda", "Agenda"),
                    ("prontuario", "Prontuário"),
                    ("orcamentos", "Orçamentos"),
                    ("financeiro", "Financeiro"),
                    ("rechamadas", "Rechamadas"),
                    ("aniversariantes", "Aniversariantes"),
                    ("convenios", "Convênios"),
                ],
                max_length=20,
                verbose_name="módulo",
            ),
        ),
        migrations.AddConstraint(
            model_name="modulodaclinica",
            constraint=models.CheckConstraint(
                condition=models.Q(codigo__in=list(CODIGOS)),
                name="modulo_clinico_conhecido",
            ),
        ),
        migrations.RunPython(ligar_modulos_gerais, remover_modulos_gerais),
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
                    "Define os tipos iniciais de atendimento. As especialidades e os módulos são "
                    "escolhidos abaixo e podem ser usados juntos."
                ),
                max_length=20,
                verbose_name="área principal",
            ),
        ),
    ]
