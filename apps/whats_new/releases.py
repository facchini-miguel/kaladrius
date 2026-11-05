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
    "novo": _("Novo"),
    "melhoria": _("Melhoria"),
    "correcao": _("Correção"),
    "seguranca": _("Segurança"),
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
AUDIENCES = {"equipe", "paciente"}
# Where an item came from (decision 133): no `origem` is a change made by the project; Dependabot
# items carry the number of their pull request, so owner and readers tell them apart.
SOURCES = {"dependabot": "Dependabot"}
REPOSITORY = "https://github.com/facchini-miguel/kaladrius"
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class InvalidReleases(ValueError):
    pass


def _in_language(textos):
    """The text in the active language, falling back to Portuguese."""
    by_language = dict(textos)
    return by_language.get(get_language()) or by_language.get(SOURCE_LANGUAGE, "")


@dataclass(frozen=True)
class Item:
    tipo: str
    modulo: str
    publico: tuple[str, ...]
    textos: tuple[tuple[str, str], ...]  # (language, text)
    origem: str = ""  # "" (the project) or a key of ORIGENS
    pr: int | None = None  # the pull request, for items from Dependabot

    @property
    def tipo_nome(self):
        return str(KINDS[self.tipo])

    @property
    def modulo_nome(self):
        return gettext(self.modulo)

    @property
    def texto(self):
        return _in_language(self.textos)

    @property
    def origem_nome(self):
        return SOURCES.get(self.origem, "")

    @property
    def pr_url(self):
        return f"{REPOSITORY}/pull/{self.pr}" if self.pr else ""


@dataclass(frozen=True)
class Release:
    versao: str
    data: datetime.date
    titulos: tuple[tuple[str, str], ...]
    itens: tuple[Item, ...]

    @property
    def titulo(self):
        return _in_language(self.titulos)

    @property
    def key(self):
        return version_tuple(self.versao)

    def items_for(self, publico):
        return tuple(item for item in self.itens if publico in item.publico)


def version_tuple(versao):
    encontrado = _SEMVER.match(str(versao))
    if not encontrado:
        raise InvalidReleases(f"Versão '{versao}' fora do formato MAIOR.MENOR.CORREÇÃO.")
    return tuple(int(parte) for parte in encontrado.groups())


def _texts(value, versao, field):
    """A text as ((language, text), ...): a plain string is Portuguese; a mapping holds
    one text per language and must include Portuguese."""
    if value is None or isinstance(value, str):
        value = {SOURCE_LANGUAGE: value or ""}
    if not isinstance(value, dict):
        raise InvalidReleases(f"{versao}: '{field}' deve ser um texto ou um texto por idioma.")
    idiomas = dict(settings.LANGUAGES)
    textos = []
    for idioma, texto in value.items():
        if idioma not in idiomas:
            raise InvalidReleases(f"{versao}: idioma '{idioma}' desconhecido em '{field}'.")
        textos.append((idioma, " ".join(str(texto or "").split())))
    if not dict(textos).get(SOURCE_LANGUAGE) and any(t for _i, t in textos):
        raise InvalidReleases(f"{versao}: '{field}' precisa do texto em português.")
    return tuple(textos)


def _validate_item(raw, versao):
    if not isinstance(raw, dict):
        raise InvalidReleases(f"{versao}: cada item deve ser um objeto.")
    tipo = raw.get("tipo")
    if tipo not in KINDS:
        raise InvalidReleases(f"{versao}: tipo '{tipo}' inválido. Use: {', '.join(KINDS)}.")
    modulo = str(raw.get("modulo") or "").strip()
    textos = _texts(raw.get("texto"), versao, "texto")
    if not modulo or not dict(textos).get(SOURCE_LANGUAGE):
        raise InvalidReleases(f"{versao}: todo item precisa de 'modulo' e 'texto'.")
    publico = raw.get("publico")
    if not isinstance(publico, list) or not set(publico) <= AUDIENCES:
        raise InvalidReleases(
            f"{versao}: 'publico' deve ser uma lista com {sorted(AUDIENCES)} (ou vazia)."
        )
    origem = raw.get("origem") or ""
    if origem and origem not in SOURCES:
        raise InvalidReleases(f"{versao}: origem '{origem}' inválida. Use: {', '.join(SOURCES)}.")
    pr = raw.get("pr")
    if pr is not None and (not isinstance(pr, int) or isinstance(pr, bool) or pr < 1):
        raise InvalidReleases(f"{versao}: 'pr' deve ser o número do pull request.")
    if origem and pr is None:
        raise InvalidReleases(f"{versao}: um item do {SOURCES[origem]} precisa do 'pr'.")
    return Item(
        tipo=tipo, modulo=modulo, publico=tuple(publico), textos=textos, origem=origem, pr=pr
    )


def _validate_release(raw):
    if not isinstance(raw, dict):
        raise InvalidReleases("Cada versão deve ser um objeto.")
    versao = str(raw.get("versao", ""))
    version_tuple(versao)
    data = raw.get("data")
    if not isinstance(data, datetime.date):
        raise InvalidReleases(f"{versao}: 'data' deve estar no formato AAAA-MM-DD.")
    itens = raw.get("itens")
    if not isinstance(itens, list) or not itens:
        raise InvalidReleases(f"{versao}: a versão precisa de pelo menos um item.")
    return Release(
        versao=versao,
        data=data,
        titulos=_texts(raw.get("titulo"), versao, "titulo"),
        itens=tuple(_validate_item(item, versao) for item in itens),
    )


def read_releases(path):
    """Read and validate the file. Versions must be ordered from newest to oldest."""
    conteudo = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(conteudo, list) or not conteudo:
        raise InvalidReleases("O arquivo deve conter uma lista com pelo menos uma versão.")
    releases = [_validate_release(raw) for raw in conteudo]
    for mais_nova, previous in zip(releases, releases[1:], strict=False):
        if mais_nova.key <= previous.key:
            raise InvalidReleases(
                f"Ordem inválida: {mais_nova.versao} deveria ser maior que {previous.versao}."
            )
        if mais_nova.data < previous.data:
            raise InvalidReleases(
                f"Data inválida: {mais_nova.versao} tem data anterior à de {previous.versao}."
            )
    return tuple(releases)


@lru_cache(maxsize=1)
def all_releases():
    return read_releases(settings.RELEASES_ARQUIVO)


def current_version():
    return all_releases()[0].versao


def has_news_for(last_seen, publico="equipe"):
    """Whether there are release notes for the audience newer than the last version seen."""
    try:
        return bool(for_audience(publico, desde=last_seen or None))
    except InvalidReleases:
        return True


def for_audience(publico, desde=None):
    """Versions with items for the audience, newest first, optionally only after `desde`."""
    minimo = version_tuple(desde) if desde else None
    resultado = []
    for release in all_releases():
        if minimo is not None and release.key <= minimo:
            continue
        itens = release.items_for(publico)
        if itens:
            resultado.append((release, itens))
    return resultado
