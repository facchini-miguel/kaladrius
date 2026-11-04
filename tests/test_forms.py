"""Django calls a form's clean_<field>() only when the form has that field: after a field is
renamed, a method left with the old name stops checking anything, with no error (decision 162,
found after clean_usuario of decision 161)."""

from django import forms

import config.urls  # noqa: F401 - imports every view, and so every form


def _subclasses(classe):
    for sub in classe.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def test_todo_clean_de_campo_tem_o_seu_campo():
    sem_campo = []
    for form in set(_subclasses(forms.BaseForm)):
        if not form.__module__.startswith("apps."):
            continue
        # A base form may leave the field to the forms built on it.
        familia = [form, *_subclasses(form)]
        for nome in vars(form):
            campo = nome.removeprefix("clean_")
            if nome.startswith("clean_") and not any(
                campo in getattr(f, "base_fields", {}) for f in familia
            ):
                sem_campo.append(f"{form.__module__}.{form.__qualname__}.{nome}")
    assert not sem_campo
