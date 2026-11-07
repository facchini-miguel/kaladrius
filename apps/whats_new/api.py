import datetime
from typing import Literal

from ninja import Router, Schema
from ninja.errors import HttpError

from . import releases

router = Router(tags=["Novidades"])


class ItemOut(Schema):
    kind: str
    kind_name: str
    module: str
    text: str
    source: str | None = None  # "Dependabot" for its updates; null for the project's own
    pr: int | None = None


class ReleaseOut(Schema):
    version: str
    date: datetime.date
    title: str
    items: list[ItemOut]


AUDIENCES = ("equipe", "paciente")


@router.get("/releases", response=list[ReleaseOut], auth=None)
def list_releases(
    request,
    audience: Literal["equipe", "paciente"] | None = None,
    since: str | None = None,
):
    """Release notes per version, newest first, in the language of Accept-Language.

    Use `since` to receive only the versions after the one the app already showed. `audience` is
    `paciente` (the default) or `equipe`.
    """
    audience = audience or "paciente"
    if audience not in AUDIENCES:
        raise HttpError(422, f"audience: use {' or '.join(AUDIENCES)}.")
    try:
        versions = releases.for_audience(audience, since=since)
    except releases.InvalidReleases as error:
        raise HttpError(400, str(error)) from error
    return [
        ReleaseOut(
            version=release.version,
            date=release.date,
            title=release.title,
            items=[
                ItemOut(
                    kind=i.kind,
                    kind_name=i.kind_name,
                    module=i.module_name,
                    text=i.text,
                    source=i.source_name or None,
                    pr=i.pr,
                )
                for i in items
            ],
        )
        for release, items in versions
    ]
