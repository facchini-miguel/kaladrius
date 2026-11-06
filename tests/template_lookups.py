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

BASELINE = Path(__file__).with_name("missing_template_variables.txt")
found_ones = set()
_original = Variable._resolve_lookup


def _recording(self, context):
    try:
        return _original(self, context)
    except VariableDoesNotExist:
        source = getattr(getattr(context, "template", None), "origin", None)
        found_ones.add(f"{getattr(source, 'template_name', None) or '?'}  {self.var}")
        raise


def install():
    Variable._resolve_lookup = _recording


def check(write):
    """At the end of the run: the new missing variables (an empty list when there are none)."""
    if os.environ.get("UPDATE_TEMPLATE_BASELINE") == "1":
        BASELINE.write_text("".join(f"{row}\n" for row in sorted(found_ones)))
        write(f"{BASELINE.name}: {len(found_ones)} entries written")
        return []
    base = set(BASELINE.read_text().splitlines())
    new_ones = sorted(found_ones - base)
    for row in new_ones:
        write(f"template variable not found (not in {BASELINE.name}): {row}")
    return new_ones
