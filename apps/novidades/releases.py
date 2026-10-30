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

TIPOS = {
    "novo": _("Novo"),
    "melhoria": _("Melhoria"),
    "correcao": _("Correção"),
    "seguranca": _("Segurança"),
}
# Modules named in releases.yaml, translated when shown (tests check every one is here).
MODULOS = [
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
    gettext_noop("Profissionais"),
    gettext_noop("Rechamadas"),
    gettext_noop("Sistema"),
    gettext_noop("Tabelas base"),
    gettext_noop("Tipos de atendimento"),
]
IDIOMA_ORIGEM = "pt-br"
PUBLICOS = {"equipe", "paciente"}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class ReleasesInvalidas(ValueError):
    pass


def _no_idioma(textos):
    """The text in the active language, falling back to Portuguese."""
    por_idioma = dict(textos)
    return por_idioma.get(get_language()) or por_idioma.get(IDIOMA_ORIGEM, "")


@dataclass(frozen=True)
class Item:
    tipo: str
    modulo: str
    publico: tuple[str, ...]
    textos: tuple[tuple[str, str], ...]  # (language, text)

    @property
    def tipo_nome(self):
        return str(TIPOS[self.tipo])

    @property
    def modulo_nome(self):
        return gettext(self.modulo)

    @property
    def texto(self):
        return _no_idioma(self.textos)


@dataclass(frozen=True)
class Release:
    versao: str
    data: datetime.date
    titulos: tuple[tuple[str, str], ...]
    itens: tuple[Item, ...]

    @property
    def titulo(self):
        return _no_idioma(self.titulos)

    @property
    def chave(self):
        return versao_para_tupla(self.versao)

    def itens_para(self, publico):
        return tuple(item for item in self.itens if publico in item.publico)


def versao_para_tupla(versao):
    encontrado = _SEMVER.match(str(versao))
    if not encontrado:
        raise ReleasesInvalidas(f"Versão '{versao}' fora do formato MAIOR.MENOR.CORREÇÃO.")
    return tuple(int(parte) for parte in encontrado.groups())


def _textos(valor, versao, campo):
    """A text as ((language, text), ...): a plain string is Portuguese; a mapping holds
    one text per language and must include Portuguese."""
    if valor is None or isinstance(valor, str):
        valor = {IDIOMA_ORIGEM: valor or ""}
    if not isinstance(valor, dict):
        raise ReleasesInvalidas(f"{versao}: '{campo}' deve ser um texto ou um texto por idioma.")
    idiomas = dict(settings.LANGUAGES)
    textos = []
    for idioma, texto in valor.items():
        if idioma not in idiomas:
            raise ReleasesInvalidas(f"{versao}: idioma '{idioma}' desconhecido em '{campo}'.")
        textos.append((idioma, " ".join(str(texto or "").split())))
    if not dict(textos).get(IDIOMA_ORIGEM) and any(t for _i, t in textos):
        raise ReleasesInvalidas(f"{versao}: '{campo}' precisa do texto em português.")
    return tuple(textos)


def _validar_item(bruto, versao):
    if not isinstance(bruto, dict):
        raise ReleasesInvalidas(f"{versao}: cada item deve ser um objeto.")
    tipo = bruto.get("tipo")
    if tipo not in TIPOS:
        raise ReleasesInvalidas(f"{versao}: tipo '{tipo}' inválido. Use: {', '.join(TIPOS)}.")
    modulo = str(bruto.get("modulo") or "").strip()
    textos = _textos(bruto.get("texto"), versao, "texto")
    if not modulo or not dict(textos).get(IDIOMA_ORIGEM):
        raise ReleasesInvalidas(f"{versao}: todo item precisa de 'modulo' e 'texto'.")
    publico = bruto.get("publico")
    if not isinstance(publico, list) or not set(publico) <= PUBLICOS:
        raise ReleasesInvalidas(
            f"{versao}: 'publico' deve ser uma lista com {sorted(PUBLICOS)} (ou vazia)."
        )
    return Item(tipo=tipo, modulo=modulo, publico=tuple(publico), textos=textos)


def _validar_release(bruto):
    if not isinstance(bruto, dict):
        raise ReleasesInvalidas("Cada versão deve ser um objeto.")
    versao = str(bruto.get("versao", ""))
    versao_para_tupla(versao)
    data = bruto.get("data")
    if not isinstance(data, datetime.date):
        raise ReleasesInvalidas(f"{versao}: 'data' deve estar no formato AAAA-MM-DD.")
    itens = bruto.get("itens")
    if not isinstance(itens, list) or not itens:
        raise ReleasesInvalidas(f"{versao}: a versão precisa de pelo menos um item.")
    return Release(
        versao=versao,
        data=data,
        titulos=_textos(bruto.get("titulo"), versao, "titulo"),
        itens=tuple(_validar_item(item, versao) for item in itens),
    )


def ler_releases(caminho):
    """Read and validate the file. Versions must be ordered from newest to oldest."""
    conteudo = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(conteudo, list) or not conteudo:
        raise ReleasesInvalidas("O arquivo deve conter uma lista com pelo menos uma versão.")
    releases = [_validar_release(bruto) for bruto in conteudo]
    for mais_nova, anterior in zip(releases, releases[1:], strict=False):
        if mais_nova.chave <= anterior.chave:
            raise ReleasesInvalidas(
                f"Ordem inválida: {mais_nova.versao} deveria ser maior que {anterior.versao}."
            )
        if mais_nova.data < anterior.data:
            raise ReleasesInvalidas(
                f"Data inválida: {mais_nova.versao} tem data anterior à de {anterior.versao}."
            )
    return tuple(releases)


@lru_cache(maxsize=1)
def todas():
    return ler_releases(settings.RELEASES_ARQUIVO)


def versao_atual():
    return todas()[0].versao


def tem_novidade_para(ultima_vista, publico="equipe"):
    """Whether there are release notes for the audience newer than the last version seen."""
    try:
        return bool(para_publico(publico, desde=ultima_vista or None))
    except ReleasesInvalidas:
        return True


def para_publico(publico, desde=None):
    """Versions with items for the audience, newest first, optionally only after `desde`."""
    minimo = versao_para_tupla(desde) if desde else None
    resultado = []
    for release in todas():
        if minimo is not None and release.chave <= minimo:
            continue
        itens = release.itens_para(publico)
        if itens:
            resultado.append((release, itens))
    return resultado
