"""Give the default accounts and categories to clinics created before this app existed.

New clinics get them from the post_save signal in apps/financeiro/signals.py.
"""

from django.db import migrations

# Frozen copies of CONTAS_PADRAO and CATEGORIAS_PADRAO at the time of this migration.
CONTAS = [("Caixa", "dinheiro"), ("Banco", "banco")]
CATEGORIAS = [
    ("Tratamento", "receita"),
    ("Consulta", "receita"),
    ("Outras receitas", "receita"),
    ("Aluguel", "despesa"),
    ("Material odontológico", "despesa"),
    ("Laboratório de prótese", "despesa"),
    ("Salários e encargos", "despesa"),
    ("Impostos", "despesa"),
    ("Água, luz e internet", "despesa"),
    ("Manutenção", "despesa"),
    ("Outras despesas", "despesa"),
]


def criar(apps, schema_editor):
    Clinica = apps.get_model("core", "Clinica")
    Conta = apps.get_model("financeiro", "Conta")
    Categoria = apps.get_model("financeiro", "Categoria")
    for clinica in Clinica.objects.all():
        if not Conta.objects.filter(clinica=clinica).exists():
            Conta.objects.bulk_create(
                Conta(clinica=clinica, nome=nome, tipo=tipo) for nome, tipo in CONTAS
            )
        if not Categoria.objects.filter(clinica=clinica).exists():
            Categoria.objects.bulk_create(
                Categoria(clinica=clinica, nome=nome, tipo=tipo) for nome, tipo in CATEGORIAS
            )


class Migration(migrations.Migration):
    dependencies = [("financeiro", "0001_initial")]

    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
