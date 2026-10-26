"""Loading and validation of the version history (releases.yaml).

Format and writing rules: docs/en/versioning-and-releases.md
"""

import datetime
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings

TIPOS = {
    "novo": "Novo",
    "melhoria": "Melhoria",
    "correcao": "Correção",
    "seguranca": "Segurança",
}
PUBLICOS = {"equipe", "paciente"}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class ReleasesInvalidas(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    tipo: str
    modulo: str
    publico: tuple[str, ...]
    texto: str

    @property
    def tipo_nome(self):
        return TIPOS[self.tipo]


@dataclass(frozen=True)
class Release:
    versao: str
    data: datetime.date
    titulo: str
    itens: tuple[Item, ...]

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


def _validar_item(bruto, versao):
    if not isinstance(bruto, dict):
        raise ReleasesInvalidas(f"{versao}: cada item deve ser um objeto.")
    tipo = bruto.get("tipo")
    if tipo not in TIPOS:
        raise ReleasesInvalidas(f"{versao}: tipo '{tipo}' inválido. Use: {', '.join(TIPOS)}.")
    modulo = str(bruto.get("modulo") or "").strip()
    texto = " ".join(str(bruto.get("texto") or "").split())
    if not modulo or not texto:
        raise ReleasesInvalidas(f"{versao}: todo item precisa de 'modulo' e 'texto'.")
    publico = bruto.get("publico")
    if not isinstance(publico, list) or not set(publico) <= PUBLICOS:
        raise ReleasesInvalidas(
            f"{versao}: 'publico' deve ser uma lista com {sorted(PUBLICOS)} (ou vazia)."
        )
    return Item(tipo=tipo, modulo=modulo, publico=tuple(publico), texto=texto)


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
        titulo=str(bruto.get("titulo") or "").strip(),
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
