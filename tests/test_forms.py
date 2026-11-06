"""Django calls a form's clean_<field>() only when the form has that field: after a field is
renamed, a method left with the old name stops checking anything, with no error (decision 162,
found after clean_usuario of decision 161)."""

from django import forms

import config.urls  # noqa: F401 - imports every view, and so every form


def _subclasses(css_class):
    for sub in css_class.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def test_every_field_clean_has_its_field():
    without_field = []
    for form in set(_subclasses(forms.BaseForm)):
        if not form.__module__.startswith("apps."):
            continue
        # A base form may leave the field to the forms built on it.
        family = [form, *_subclasses(form)]
        for name in vars(form):
            field = name.removeprefix("clean_")
            if name.startswith("clean_") and not any(
                field in getattr(f, "base_fields", {}) for f in family
            ):
                without_field.append(f"{form.__module__}.{form.__qualname__}.{name}")
    assert not without_field
