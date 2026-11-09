"""Category.key (decision 205): which default category each one is, so the code finds the
payroll and the commissions categories without looking for their Portuguese names.

Every clinic created so far got its defaults in Portuguese; a category the clinic renamed
keeps an empty key, as one it added itself.
"""

from django.db import migrations, models
from django.db.models import Q

# Frozen copy of the default names before decision 205, by kind.
KEYS = {
    ("income", "Tratamento"): "treatment",
    ("income", "Consulta"): "consultation",
    ("income", "Outras receitas"): "other_income",
    ("expense", "Aluguel"): "rent",
    ("expense", "Material odontológico"): "dental_supplies",
    ("expense", "Laboratório de prótese"): "prosthesis_lab",
    ("expense", "Salários e encargos"): "payroll",
    ("expense", "Comissões"): "commissions",
    ("expense", "Impostos"): "taxes",
    ("expense", "Água, luz e internet"): "utilities",
    ("expense", "Manutenção"): "maintenance",
    ("expense", "Outras despesas"): "other_expenses",
}


def fill(apps, schema_editor):
    Category = apps.get_model("finance", "Category")
    for (kind, name), key in KEYS.items():
        Category.objects.filter(kind=kind, name=name).update(key=key)


class Migration(migrations.Migration):
    dependencies = [("finance", "0029_english_texts")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="key",
            field=models.CharField(blank=True, editable=False, max_length=30),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                condition=~Q(key=""), fields=("clinic", "key"), name="category_key_unique"
            ),
        ),
    ]
