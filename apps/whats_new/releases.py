"""Loading and validation of the version history (releases.yaml).

Format and writing rules: docs/docs/project/versioning.md
"""

import datetime
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings
from django.utils.translation import get_language, gettext, gettext_noop
from django.utils.translation import gettext_lazy as _

KINDS = {
    "new": _("Novo"),
    "improvement": _("Melhoria"),
    "fix": _("Correção"),
    "security": _("Segurança"),
}
# Modules named in releases.yaml, translated when shown (tests check every one is here).
MODULES = [
    gettext_noop("Acesso"),
    gettext_noop("Ajuda"),
    gettext_noop("Agenda"),
    gettext_noop("Aniversariantes"),
    gettext_noop("Auditoria"),
    gettext_noop("Cadastros"),
    gettext_noop("Clínica"),
    gettext_noop("Clínicas"),
    gettext_noop("Convênios"),
    gettext_noop("Documentação"),
    gettext_noop("Equipe"),
    gettext_noop("Financeiro"),
    gettext_noop("Geral"),
    gettext_noop("Idioma"),
    gettext_noop("Novidades"),
    gettext_noop("Orçamentos"),
    gettext_noop("Pacientes"),
    gettext_noop("Permissões"),
    gettext_noop("Pessoal"),
    gettext_noop("Profissionais"),
    gettext_noop("Rechamadas"),
    gettext_noop("Sistema"),
    gettext_noop("Tabelas base"),
    gettext_noop("Tipos de atendimento"),
]
SOURCE_LANGUAGE = "pt-br"
AUDIENCES = {"staff", "patient"}
# Where an item came from (decision 133): no `origem` is a change made by the project; Dependabot
# items carry the number of their pull request, so owner and readers tell them apart.
SOURCES = {"dependabot": "Dependabot"}
REPOSITORY = "https://github.com/facchini-miguel/kaladrius"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class InvalidReleases(ValueError):
    pass


def _in_language(texts):
    """The text in the active language, falling back to Portuguese."""
    by_language = dict(texts)
    return by_language.get(get_language()) or by_language.get(SOURCE_LANGUAGE, "")


@dataclass(frozen=True)
class Item:
    kind: str
    module: str
    audience: tuple[str, ...]
    texts: tuple[tuple[str, str], ...]  # (language, text)
    source: str = ""  # "" (the project) or a key of SOURCES
    pr: int | None = None  # the pull request, for items from Dependabot

    @property
    def kind_name(self):
        return str(KINDS[self.kind])

    @property
    def module_name(self):
        return gettext(self.module)

    @property
    def text(self):
        return _in_language(self.texts)

    @property
    def source_name(self):
        return SOURCES.get(self.source, "")

    @property
    def pr_url(self):
        return f"{REPOSITORY}/pull/{self.pr}" if self.pr else ""


@dataclass(frozen=True)
class Release:
    version: str
    date: datetime.date
    titles: tuple[tuple[str, str], ...]
    items: tuple[Item, ...]

    @property
    def title(self):
        return _in_language(self.titles)

    @property
    def key(self):
        return version_tuple(self.version)

    def items_for(self, audience):
        return tuple(item for item in self.items if audience in item.audience)


def version_tuple(version):
    found = _SEMVER.match(str(version))
    if not found:
        raise InvalidReleases(f"Versão '{version}' fora do formato MAIOR.MENOR.CORREÇÃO.")
    return tuple(int(part) for part in found.groups())


def _texts(value, version, field):
    """A text as ((language, text), ...): a plain string is Portuguese; a mapping holds
    one text per language and must include Portuguese."""
    if value is None or isinstance(value, str):
        value = {SOURCE_LANGUAGE: value or ""}
    if not isinstance(value, dict):
        raise InvalidReleases(f"{version}: '{field}' deve ser um texto ou um texto por idioma.")
    languages = dict(settings.LANGUAGES)
    texts = []
    for language, text in value.items():
        if language not in languages:
            raise InvalidReleases(f"{version}: idioma '{language}' desconhecido em '{field}'.")
        texts.append((language, " ".join(str(text or "").split())))
    if not dict(texts).get(SOURCE_LANGUAGE) and any(t for _i, t in texts):
        raise InvalidReleases(f"{version}: '{field}' precisa do texto em português.")
    return tuple(texts)


# The fields of a version and of an item (decision 189: in English since 0.60.0, so an entry
# written in the old format, with `versao` or `tipo`, is refused with the field to rename).
RELEASE_FIELDS = {"version", "date", "title", "items"}
ITEM_FIELDS = {"kind", "module", "audience", "text", "source", "pr"}


def _known_fields(raw, fields, version):
    unknown = sorted(set(raw) - fields)
    if unknown:
        raise InvalidReleases(
            f"{version}: campo(s) desconhecido(s): {', '.join(unknown)}. "
            f"Use: {', '.join(sorted(fields))}."
        )


def _validate_item(raw, version):
    if not isinstance(raw, dict):
        raise InvalidReleases(f"{version}: cada item deve ser um objeto.")
    _known_fields(raw, ITEM_FIELDS, version)
    kind = raw.get("kind")
    if kind not in KINDS:
        raise InvalidReleases(f"{version}: tipo '{kind}' inválido. Use: {', '.join(KINDS)}.")
    module = str(raw.get("module") or "").strip()
    texts = _texts(raw.get("text"), version, "text")
    if not module or not dict(texts).get(SOURCE_LANGUAGE):
        raise InvalidReleases(f"{version}: todo item precisa de 'module' e 'text'.")
    audience = raw.get("audience")
    if not isinstance(audience, list) or not set(audience) <= AUDIENCES:
        raise InvalidReleases(
            f"{version}: 'audience' deve ser uma lista com {sorted(AUDIENCES)} (ou vazia)."
        )
    source = raw.get("source") or ""
    if source and source not in SOURCES:
        raise InvalidReleases(f"{version}: origem '{source}' inválida. Use: {', '.join(SOURCES)}.")
    pr = raw.get("pr")
    if pr is not None and (not isinstance(pr, int) or isinstance(pr, bool) or pr < 1):
        raise InvalidReleases(f"{version}: 'pr' deve ser o número do pull request.")
    if source and pr is None:
        raise InvalidReleases(f"{version}: um item do {SOURCES[source]} precisa do 'pr'.")
    return Item(
        kind=kind, module=module, audience=tuple(audience), texts=texts, source=source, pr=pr
    )


def _validate_release(raw):
    if not isinstance(raw, dict):
        raise InvalidReleases("Cada versão deve ser um objeto.")
    version = str(raw.get("version", ""))
    _known_fields(raw, RELEASE_FIELDS, version or "?")
    version_tuple(version)
    date = raw.get("date")
    if not isinstance(date, datetime.date):
        raise InvalidReleases(f"{version}: 'date' deve estar no formato AAAA-MM-DD.")
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        raise InvalidReleases(f"{version}: a versão precisa de pelo menos um item.")
    return Release(
        version=version,
        date=date,
        titles=_texts(raw.get("title"), version, "title"),
        items=tuple(_validate_item(item, version) for item in items),
    )


def read_releases(path):
    """Read and validate the file. Versions must be ordered from newest to oldest."""
    content = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(content, list) or not content:
        raise InvalidReleases("O arquivo deve conter uma lista com pelo menos uma versão.")
    releases = [_validate_release(raw) for raw in content]
    for newer, previous in zip(releases, releases[1:], strict=False):
        if newer.key <= previous.key:
            raise InvalidReleases(
                f"Ordem inválida: {newer.version} deveria ser maior que {previous.version}."
            )
        if newer.date < previous.date:
            raise InvalidReleases(
                f"Data inválida: {newer.version} tem data anterior à de {previous.version}."
            )
    return tuple(releases)


@lru_cache(maxsize=1)
def all_releases():
    return read_releases(settings.RELEASES_FILE)


def current_version():
    return all_releases()[0].version


def has_news_for(last_seen, audience="staff"):
    """Whether there are release notes for the audience newer than the last version seen."""
    try:
        return bool(for_audience(audience, since=last_seen or None))
    except InvalidReleases:
        return True


def for_audience(audience, since=None):
    """Versions with items for the audience, newest first, optionally only after `since`."""
    minimum = version_tuple(since) if since else None
    result = []
    for release in all_releases():
        if minimum is not None and release.key <= minimum:
            continue
        items = release.items_for(audience)
        if items:
            result.append((release, items))
    return result
