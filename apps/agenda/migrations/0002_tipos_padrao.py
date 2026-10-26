"""Give the default appointment types to clinics created before this app existed.

New clinics get them from the post_save signal in apps/agenda/signals.py.
"""

from django.db import migrations

# Frozen copy of TIPOS_PADRAO at the time of this migration.
TIPOS_PADRAO = [
    ("Liberado", "#b9f1a7"),
    ("Cirurgia", "#f7a5a5"),
    ("Dentística", "#f6f7a5"),
    ("Periodontia", "#7b88cb"),
    ("Consulta inicial", "#e7a5f7"),
    ("Prótese", "#fed27d"),
    ("Endodontia", "#e96cd9"),
    ("Ortodontia", "#a7eef1"),
    ("Atendimento de 15 em 15", "#d5dae6"),
    ("Ocupado", "#a7bef1"),
]


def criar(apps, schema_editor):
    Clinica = apps.get_model("core", "Clinica")
    TipoAtendimento = apps.get_model("agenda", "TipoAtendimento")
    for clinica in Clinica.objects.all():
        if not TipoAtendimento.objects.filter(clinica=clinica).exists():
            TipoAtendimento.objects.bulk_create(
                TipoAtendimento(clinica=clinica, nome=nome, cor=cor) for nome, cor in TIPOS_PADRAO
            )


class Migration(migrations.Migration):
    dependencies = [("agenda", "0001_initial")]

    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
