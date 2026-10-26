"""Load the official reference data (IBGE states and cities, Banco Central banks)."""

import json
from pathlib import Path

from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations

DADOS = Path(__file__).resolve().parent.parent / "dados"

ESTADOS_CIVIS = [
    "Solteiro(a)",
    "Casado(a)",
    "União estável",
    "Separado(a)",
    "Divorciado(a)",
    "Viúvo(a)",
]


def _ler(nome):
    return json.loads((DADOS / f"{nome}.json").read_text(encoding="utf-8"))


def carregar(apps, schema_editor):
    UF = apps.get_model("referencias", "UF")
    Cidade = apps.get_model("referencias", "Cidade")
    Banco = apps.get_model("referencias", "Banco")
    EstadoCivil = apps.get_model("referencias", "EstadoCivil")

    UF.objects.bulk_create(UF(**uf) for uf in _ler("ufs"))
    Cidade.objects.bulk_create(
        (Cidade(codigo=c["codigo"], nome=c["nome"], uf_id=c["uf"]) for c in _ler("cidades")),
        batch_size=1000,
    )
    Banco.objects.bulk_create(Banco(**banco) for banco in _ler("bancos"))
    EstadoCivil.objects.bulk_create(
        EstadoCivil(nome=nome, ordem=ordem) for ordem, nome in enumerate(ESTADOS_CIVIS, start=1)
    )


def remover(apps, schema_editor):
    for modelo in ["EstadoCivil", "Banco", "Cidade", "UF"]:
        apps.get_model("referencias", modelo).objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("referencias", "0001_initial")]

    operations = [
        UnaccentExtension(),
        migrations.RunPython(carregar, remover),
    ]
