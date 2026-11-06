"""A renamed field keeps a Portuguese label (decision 170).

Without verbose_name, Django builds the label from the field's name: once the name is English
("created_by"), the screens and the audit show "created by". Every field of the project's
models must therefore say its label itself (decision 179 removed the db_column pins that
used to mark the renamed ones).
"""

from django.apps import apps


def test_renamed_field_has_its_own_label():
    without_label = [
        f"{template_._meta.label}.{field.name}"
        for template_ in apps.get_models()
        if template_.__module__.startswith("apps.")
        for field in template_._meta.get_fields()
        if getattr(field, "concrete", False)
        and not field.auto_created
        and getattr(field, "db_column", None)
        and str(field.verbose_name) == field.name.replace("_", " ")
    ]
    assert not without_label, (
        f"label from the English name, give it a verbose_name: {without_label}"
    )
