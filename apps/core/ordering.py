"""Alphabetical order as people expect it: "Água" next to "Ana", not after "Zeca".

The database image (postgres:16-alpine) sorts text by its bytes, since musl has no
locale collation: accented and lowercase names went to the end of every list. Name
columns use the ICU root collation instead (decision 103), which sorts Portuguese,
Spanish and English names correctly and is deterministic, so equality and unique
constraints behave as before.
"""

import unicodedata

ALPHABETICAL = "und-x-icu"


def alphabetical_key(text):
    """Sort key for Python lists of names, matching the database order closely enough:
    accents and case are ignored."""
    sem_acento = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()
