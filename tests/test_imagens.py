"""Base images pinned by digest (decision 138): a tag such as python:3.14-slim or caddy:2-alpine
is moved by its publisher when the image is rebuilt, so the same commit could build or run
something else next week. Every base image names its digest; Dependabot proposes new ones.
The project's own images (${IMAGEM_APP}, ${IMAGEM_DOCS}) are excluded: CI builds them."""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _imagens():
    for arquivo in ("Dockerfile", "docs/Dockerfile"):
        for linha in (RAIZ / arquivo).read_text().splitlines():
            if linha.startswith("FROM "):
                yield arquivo, linha.split()[1]
    for arquivo in ("docker-compose.yml", "deploy/docker-compose.prod.yml"):
        for linha in (RAIZ / arquivo).read_text().splitlines():
            if m := re.match(r"\s+image:\s*(\S+)", linha):
                if not m[1].startswith("${"):
                    yield arquivo, m[1]


@pytest.mark.parametrize(("arquivo", "imagem"), list(_imagens()))
def test_imagem_de_base_fixada_por_digest(arquivo, imagem):
    assert DIGEST.search(imagem), f"{arquivo}: {imagem} needs @sha256:<digest> (decision 138)"


def test_mesma_imagem_em_todo_lugar():
    """The same base image (Caddy, PostgreSQL) has the same digest wherever it is used."""
    por_nome = {}
    for _arquivo, imagem in _imagens():
        nome, digest = imagem.split("@")
        por_nome.setdefault(nome, set()).add(digest)
    divergentes = {nome: d for nome, d in por_nome.items() if len(d) > 1}
    assert not divergentes, divergentes
