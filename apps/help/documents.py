"""The documentation site (docs/, decision 073) as seen from inside the system.

Only the privacy policy is shown inside the system: it is public (patients do not log in)
and shows the clinic's contact. Everything else, from the user manual to the installation
guide, is a link to the site (settings.DOCS_URL) in the user's language.
"""

import re
from pathlib import Path

import markdown
from django.conf import settings
from django.utils.translation import get_language

DOCS = Path(settings.BASE_DIR) / "docs"
# Interface language -> the site's folder with that language's pages, and its URL prefix.
PASTAS = {
    "pt-br": "i18n/pt-BR/docusaurus-plugin-content-docs/current",
    "en": "docs",
    "es": "i18n/es/docusaurus-plugin-content-docs/current",
}
PREFIXOS = {"pt-br": "/pt-BR", "en": "", "es": "/es"}
IDIOMA_PADRAO = "pt-br"

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_ITEM_DE_LISTA = re.compile(r"^\s*(?:[-*+] |\d+\. )")


def _idioma():
    language = get_language()
    return language if language in PASTAS else IDIOMA_PADRAO


def url_do_site(path=""):
    """Address of a page of the documentation site in the current language."""
    return f"{settings.DOCS_URL.rstrip('/')}{PREFIXOS[_idioma()]}/{path}"


def _separar_listas(text):
    """Blank line before a list that follows a paragraph line, outside code blocks.

    GitHub and the site render such lists, but Python-Markdown needs the blank line.
    """
    rows, em_codigo, previous = [], False, ""
    for row in text.split("\n"):
        if row.lstrip().startswith("```"):
            em_codigo = not em_codigo
        elif (
            not em_codigo
            and _ITEM_DE_LISTA.match(row)
            and previous.strip()
            and not _ITEM_DE_LISTA.match(previous)
            and not previous.startswith((" ", "|", ">", "#"))
        ):
            rows.append("")
        rows.append(row)
        previous = row
    return "\n".join(rows)


def privacidade():
    """(title, HTML) of the privacy policy in the current language."""
    file = DOCS / PASTAS[_idioma()] / "manual" / "privacy.md"
    text = _FRONTMATTER.sub("", file.read_text(encoding="utf-8"), count=1)
    titulo = next((row[2:].strip() for row in text.splitlines() if row.startswith("# ")), "")
    html = markdown.markdown(
        _separar_listas(text), extensions=["tables", "fenced_code", "sane_lists"]
    )
    html = html.replace("<table>", '<table class="table table-sm table-bordered bg-white">')
    return titulo, html
