"""A renamed field keeps a Portuguese label (decision 170).

Without verbose_name, Django builds the label from the field's name: once the name is English
("created_by"), the screens and the audit show "created by". Every field whose column was
pinned by a rename (db_column) must therefore say its label itself.
"""

from django.apps import apps


def test_campo_renomeado_tem_rotulo_proprio():
    sem_rotulo = [
        f"{modelo._meta.label}.{campo.name}"
        for modelo in apps.get_models()
        if modelo.__module__.startswith("apps.")
        for campo in modelo._meta.get_fields()
        if getattr(campo, "concrete", False)
        and not campo.auto_created
        and getattr(campo, "db_column", None)
        and str(campo.verbose_name) == campo.name.replace("_", " ")
    ]
    assert not sem_rotulo, f"label from the English name, give it a verbose_name: {sem_rotulo}"
