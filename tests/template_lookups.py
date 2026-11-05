"""Template variables that do not exist (decision 159). Django shows a missing variable as an
empty text, with no error: after renaming a field or a context variable, a forgotten
`{{ paciente.nome }}` would only show as a blank on screen. The tests record every variable a
template looks up and does not find, and fail on one that is not in
missing_template_variables.txt: the ones missing today on purpose (an optional context
variable, `{% if x %}` on something that may not be there).

UPDATE_TEMPLATE_BASELINE=1 rewrites the file from a full run; review its diff: a rename keeps
the same entries, with the new names.
"""

import os
from pathlib import Path

from django.template.base import Variable, VariableDoesNotExist

LINHA_DE_BASE = Path(__file__).with_name("missing_template_variables.txt")
encontradas = set()
_original = Variable._resolve_lookup


def _registrando(self, context):
    try:
        return _original(self, context)
    except VariableDoesNotExist:
        source = getattr(getattr(context, "template", None), "origin", None)
        encontradas.add(f"{getattr(source, 'template_name', None) or '?'}  {self.var}")
        raise


def instalar():
    Variable._resolve_lookup = _registrando


def conferir(escrever):
    """At the end of the run: the new missing variables (an empty list when there are none)."""
    if os.environ.get("UPDATE_TEMPLATE_BASELINE") == "1":
        LINHA_DE_BASE.write_text("".join(f"{row}\n" for row in sorted(encontradas)))
        escrever(f"{LINHA_DE_BASE.name}: {len(encontradas)} entries written")
        return []
    base = set(LINHA_DE_BASE.read_text().splitlines())
    novas = sorted(encontradas - base)
    for row in novas:
        escrever(f"template variable not found (not in {LINHA_DE_BASE.name}): {row}")
    return novas
