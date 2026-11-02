"""Base images pinned by digest (decision 138): a tag such as python:3.14-slim or caddy:2-alpine
is moved by its publisher when the image is rebuilt, so the same commit could build or run
something else next week. Every base image names its digest; Dependabot proposes new ones.
The project's own images (${IMAGEM_APP}, ${IMAGEM_DOCS}) are excluded: CI builds them.

Every Dockerfile and Compose file of the repository is read (Compose as YAML, so quoting and
layout do not matter), and the scripts and workflows that start these images must not name
them by a bare tag: they read the pinned image from the Dockerfile or the production Compose
file instead."""

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
FORA = {".git", "node_modules", ".venv", "venv", "build", ".docusaurus"}


def _arquivos(*padroes):
    vistos = set()
    for padrao in padroes:
        for arquivo in sorted(RAIZ.rglob(padrao)):
            if arquivo not in vistos and not FORA.intersection(arquivo.relative_to(RAIZ).parts):
                vistos.add(arquivo)
                yield arquivo


def _from_do_dockerfile(texto):
    """Images of the FROM lines: any case, continued lines joined, --platform and other flags
    skipped, and earlier stages (FROM build) and scratch left out."""
    estagios = {"scratch"}
    for instrucao in re.sub(r"\\\n", " ", texto).splitlines():
        partes = instrucao.split()
        if not partes or partes[0].upper() != "FROM":
            continue
        resto = [p for p in partes[1:] if not p.startswith("--")]
        if len(resto) >= 3 and resto[1].upper() == "AS":
            estagios.add(resto[2].lower())
        if resto and resto[0].lower() not in estagios:
            yield resto[0]


def _imagens_do_compose(texto):
    servicos = (yaml.safe_load(texto) or {}).get("services") or {}
    for servico in servicos.values():
        imagem = str((servico or {}).get("image") or "")
        if imagem and not imagem.startswith("${"):
            yield imagem


def _imagens():
    for arquivo in _arquivos("Dockerfile", "*.Dockerfile", "Dockerfile.*"):
        for imagem in _from_do_dockerfile(arquivo.read_text()):
            yield arquivo.relative_to(RAIZ).as_posix(), imagem
    for arquivo in _arquivos("docker-compose*.yml", "docker-compose*.yaml", "compose*.y*ml"):
        for imagem in _imagens_do_compose(arquivo.read_text()):
            yield arquivo.relative_to(RAIZ).as_posix(), imagem


def _repositorio(imagem):
    """postgres:16-alpine@sha256:… -> postgres (a registry port, as in host:5000/x, is kept)."""
    partes = imagem.partition("@")[0].rsplit("/", 1)
    partes[-1] = partes[-1].partition(":")[0]
    return "/".join(partes)


IMAGENS = list(_imagens())


def test_encontra_as_imagens_do_sistema():
    """The scan sees the system image and production's database and Caddy (the docs site's
    Dockerfile is not inside the system image, so it is not required)."""
    arquivos = {arquivo for arquivo, _imagem in IMAGENS}
    assert {"Dockerfile", "docker-compose.yml", "deploy/docker-compose.prod.yml"} <= arquivos
    producao = {_repositorio(i) for a, i in IMAGENS if a == "deploy/docker-compose.prod.yml"}
    assert {"postgres", "caddy"} <= producao


@pytest.mark.parametrize(("arquivo", "imagem"), IMAGENS)
def test_imagem_de_base_fixada_por_digest(arquivo, imagem):
    assert DIGEST.search(imagem), f"{arquivo}: {imagem} needs @sha256:<digest> (decision 138)"


def test_mesma_imagem_nos_arquivos_do_compose():
    """Development and production run the same PostgreSQL. Only the Compose files are compared:
    Dependabot updates them in one pull request (the imagens-compose group), while the docs
    site's Caddy, in a Dockerfile, gets its own and may differ from production's for a while."""
    por_repositorio = {}
    for arquivo, imagem in IMAGENS:
        if "compose" in Path(arquivo).name:
            por_repositorio.setdefault(_repositorio(imagem), {})[arquivo] = imagem
    divergentes = {r: a for r, a in por_repositorio.items() if len(set(a.values())) > 1}
    assert not divergentes, divergentes


def test_scripts_e_ci_nao_usam_tag_solta():
    """The scripts and workflows that start a base image (the restore tests, the lock
    generator, CI's PostgreSQL) read it, digest included, from the Dockerfile or the production
    Compose file, never by a bare tag such as postgres:16-alpine."""
    repositorios = "|".join(sorted({re.escape(_repositorio(i)) for _a, i in IMAGENS}))
    solta = re.compile(rf"(?<![\w/.-])(?:{repositorios}):[\w.${{}}-]+(?!\S*@sha256:)")
    achados = []
    for arquivo in _arquivos("*.sh", "*.yml", "*.yaml"):
        if "compose" in arquivo.name or arquivo.name == "releases.yaml":
            continue
        for numero, linha in enumerate(arquivo.read_text().splitlines(), 1):
            codigo = linha.split(" #", 1)[0]
            if codigo.lstrip().startswith("#"):
                continue
            local = arquivo.relative_to(RAIZ)
            achados += [f"{local}:{numero}: {m[0]}" for m in solta.finditer(codigo)]
    assert not achados, achados


@pytest.mark.parametrize(
    ("dockerfile", "esperado"),
    [
        ("FROM python:3@sha256:a\n", ["python:3@sha256:a"]),
        ("from node:26 AS build\nFROM build\n", ["node:26"]),
        ("FROM --platform=$BUILDPLATFORM node:26 AS b\nFROM caddy:2\n", ["node:26", "caddy:2"]),
        ("FROM \\\n  caddy:2\nRUN x\n", ["caddy:2"]),
        ("FROM scratch\n# FROM nada:1\n", []),
    ],
)
def test_leitura_do_from(dockerfile, esperado):
    assert list(_from_do_dockerfile(dockerfile)) == esperado


@pytest.mark.parametrize(
    ("imagem", "repositorio"),
    [
        ("postgres:16-alpine@sha256:abc", "postgres"),
        ("caddy", "caddy"),
        ("registro:5000/eu/app:1", "registro:5000/eu/app"),
        ("ghcr.io/x/y@sha256:abc", "ghcr.io/x/y"),
    ],
)
def test_repositorio(imagem, repositorio):
    assert _repositorio(imagem) == repositorio
