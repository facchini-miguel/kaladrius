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


class ReleaseOut(Schema):
    versao: str
    data: datetime.date
    titulo: str
    itens: list[ItemOut]


@router.get("/releases", response=list[ReleaseOut], auth=None)
def listar_releases(
    request, publico: Literal["equipe", "paciente"] = "paciente", desde: str | None = None
):
    """Novidades por versão, da mais nova para a mais antiga.

    Use `desde` para receber só as versões posteriores à que o app já mostrou.
    """
    try:
        versoes = releases.para_publico(publico, desde=desde)
    except releases.ReleasesInvalidas as erro:
        raise HttpError(400, str(erro)) from erro
    return [
        ReleaseOut(
            versao=release.versao,
            data=release.data,
            titulo=release.titulo,
            itens=[
                ItemOut(tipo=i.tipo, tipo_nome=i.tipo_nome, modulo=i.modulo, texto=i.texto)
                for i in itens
            ],
        )
        for release, itens in versoes
    ]
