"""A renamed field keeps a Portuguese label (decision 170).

Without verbose_name, Django builds the label from the field's name: once the name is English
("created_by"), the screens and the audit show "created by". Every field of the project's
models must therefore say its label itself (decision 179 removed the db_column pins that
used to mark the renamed ones).
"""

from django.apps import apps


def test_campo_renomeado_tem_rotulo_proprio():
    sem_rotulo = [
        f"{modelo._meta.label}.{field.name}"
        for modelo in apps.get_models()
        if modelo.__module__.startswith("apps.")
        for field in modelo._meta.get_fields()
        if getattr(field, "concrete", False)
        and not field.auto_created
        and getattr(field, "db_column", None)
        and str(field.verbose_name) == field.name.replace("_", " ")
    ]
    assert not sem_rotulo, f"label from the English name, give it a verbose_name: {sem_rotulo}"
