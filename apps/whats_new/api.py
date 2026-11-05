import datetime
from typing import Literal

from ninja import Router, Schema
from ninja.errors import HttpError

from . import releases

router = Router(tags=["Novidades"])


class ItemOut(Schema):
    tipo: str
    tipo_nome: str
    modulo: str
    texto: str
    origem: str | None = None  # "Dependabot" for its updates; null for the project's own
    pr: int | None = None


class ReleaseOut(Schema):
    versao: str
    data: datetime.date
    titulo: str
    itens: list[ItemOut]


@router.get("/releases", response=list[ReleaseOut], auth=None)
def list_releases(
    request, publico: Literal["equipe", "paciente"] = "paciente", desde: str | None = None
):
    """Release notes per version, newest first, in the language of Accept-Language.

    Use `desde` to receive only the versions after the one the app already showed.
    """
    try:
        versions = releases.for_audience(publico, desde=desde)
    except releases.InvalidReleases as error:
        raise HttpError(400, str(error)) from error
    return [
        ReleaseOut(
            versao=release.versao,
            data=release.data,
            titulo=release.titulo,
            itens=[
                ItemOut(
                    tipo=i.tipo,
                    tipo_nome=i.tipo_nome,
                    modulo=i.modulo_nome,
                    texto=i.texto,
                    origem=i.origem_nome or None,
                    pr=i.pr,
                )
                for i in itens
            ],
        )
        for release, itens in versions
    ]
