"""Give clinics that already have categories the new default "Comissões" (0.19.0)."""

from django.db import migrations


def criar(apps, schema_editor):
    Categoria = apps.get_model("financeiro", "Categoria")
    clinicas = Categoria.objects.values_list("clinica_id", flat=True).distinct()
    for clinica_id in clinicas:
        Categoria.objects.get_or_create(clinica_id=clinica_id, tipo="despesa", nome="Comissões")


class Migration(migrations.Migration):
    dependencies = [("financeiro", "0005_comissao")]

    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
