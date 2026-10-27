"""Markdown documents from docs/ shown inside the system (decision 050).

The user manual lives in docs/<language>/manual/ with the same file names in every
language. The technical documentation (the rest of docs/) is shown to superusers only:
it describes the infrastructure. Links between documents become links inside the
system; other files of the repository link to GitHub.
"""

import posixpath
import re
from pathlib import Path

import markdown
from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language

DOCS = Path(settings.BASE_DIR) / "docs"
REPOSITORIO = "https://github.com/facchini-miguel/medical-system/blob/main/"
# Interface language -> docs folder.
PASTAS = {"pt-br": "pt-BR", "en": "en", "es": "es"}
# Manual pages in reading order (file names, the same in every language).
MANUAL = [
    "inicio",
    "agenda",
    "pacientes",
    "orcamentos",
    "rechamadas",
    "financeiro",
    "equipe",
    "clinica",
    "privacidade",
]

_LINK = re.compile(r'(<a\s+href=")([^"]+)(")')
_ITEM_DE_LISTA = re.compile(r"^\s*(?:[-*+] |\d+\. )")


class DocumentoNaoEncontrado(Exception):
    pass


def pasta_do_idioma():
    return PASTAS.get(get_language(), "pt-BR")


def _resolver(atual, destino):
    """Path inside docs/ (e.g. "en/deploy.md") a relative link points to, or None."""
    caminho = posixpath.normpath(posixpath.join(posixpath.dirname(atual), destino))
    return None if caminho.startswith("..") else caminho


def _link(atual, href, tecnica):
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href
    alvo, _sep, ancora = href.partition("#")
    ancora = f"#{ancora}" if ancora else ""
    caminho = _resolver(atual, alvo)
    if caminho is None:
        # Outside docs/: another file of the repository.
        repositorio = posixpath.normpath(posixpath.join("docs", posixpath.dirname(atual), alvo))
        return REPOSITORIO + repositorio + ancora
    if not caminho.endswith(".md"):
        return REPOSITORIO + "docs/" + caminho + ancora
    partes = caminho.split("/")
    if len(partes) == 3 and partes[1] == "manual" and partes[2][:-3] in MANUAL:
        return reverse("ajuda:manual", args=[partes[2][:-3]]) + ancora
    if tecnica:
        return reverse("ajuda:tecnica", args=[caminho]) + ancora
    return REPOSITORIO + "docs/" + caminho + ancora


def _separar_listas(texto):
    """Blank line before a list that follows a paragraph line, outside code blocks.

    GitHub renders such lists, but Python-Markdown needs the blank line.
    """
    linhas, em_codigo, anterior = [], False, ""
    for linha in texto.split("\n"):
        if linha.lstrip().startswith("```"):
            em_codigo = not em_codigo
        elif (
            not em_codigo
            and _ITEM_DE_LISTA.match(linha)
            and anterior.strip()
            and not _ITEM_DE_LISTA.match(anterior)
            and not anterior.startswith((" ", "|", ">", "#"))
        ):
            linhas.append("")
        linhas.append(linha)
        anterior = linha
    return "\n".join(linhas)


def renderizar(caminho, tecnica=False):
    """(title, HTML) of docs/<caminho>. Raises DocumentoNaoEncontrado."""
    arquivo = (DOCS / caminho).resolve()
    if DOCS.resolve() not in arquivo.parents or arquivo.suffix != ".md" or not arquivo.is_file():
        raise DocumentoNaoEncontrado(caminho)
    texto = arquivo.read_text(encoding="utf-8")
    titulo = next((linha[2:].strip() for linha in texto.splitlines() if linha.startswith("# ")), "")
    html = markdown.markdown(
        _separar_listas(texto), extensions=["tables", "fenced_code", "sane_lists"]
    )
    html = _LINK.sub(lambda m: m.group(1) + _link(caminho, m.group(2), tecnica) + m.group(3), html)
    html = html.replace("<table>", '<table class="table table-sm table-bordered bg-white">')
    return titulo, html


def manual(pagina):
    """(title, HTML) of a manual page in the current language (Portuguese as fallback)."""
    if pagina not in MANUAL:
        raise DocumentoNaoEncontrado(pagina)
    for pasta in (pasta_do_idioma(), "pt-BR"):
        try:
            return renderizar(f"{pasta}/manual/{pagina}.md")
        except DocumentoNaoEncontrado:
            continue
    raise DocumentoNaoEncontrado(pagina)


def indice_do_manual():
    """[(page, title)] in reading order."""
    return [(pagina, manual(pagina)[0]) for pagina in MANUAL]
