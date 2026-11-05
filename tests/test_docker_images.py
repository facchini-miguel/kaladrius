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
    for default in padroes:
        for file in sorted(RAIZ.rglob(default)):
            if file not in vistos and not FORA.intersection(file.relative_to(RAIZ).parts):
                vistos.add(file)
                yield file


def _from_do_dockerfile(text):
    """Images of the FROM lines: any case, continued lines joined, --platform and other flags
    skipped, and earlier stages (FROM build) and scratch left out."""
    estagios = {"scratch"}
    for instrucao in re.sub(r"\\\n", " ", text).splitlines():
        partes = instrucao.split()
        if not partes or partes[0].upper() != "FROM":
            continue
        resto = [p for p in partes[1:] if not p.startswith("--")]
        if len(resto) >= 3 and resto[1].upper() == "AS":
            estagios.add(resto[2].lower())
        if resto and resto[0].lower() not in estagios:
            yield resto[0]


def _imagens_do_compose(text):
    servicos = (yaml.safe_load(text) or {}).get("services") or {}
    for servico in servicos.values():
        imagem = str((servico or {}).get("image") or "")
        if imagem and not imagem.startswith("${"):
            yield imagem


def _imagens():
    for file in _arquivos("Dockerfile", "*.Dockerfile", "Dockerfile.*"):
        for imagem in _from_do_dockerfile(file.read_text()):
            yield file.relative_to(RAIZ).as_posix(), imagem
    for file in _arquivos("docker-compose*.yml", "docker-compose*.yaml", "compose*.y*ml"):
        for imagem in _imagens_do_compose(file.read_text()):
            yield file.relative_to(RAIZ).as_posix(), imagem


def _repositorio(imagem):
    """postgres:16-alpine@sha256:… -> postgres (a registry port, as in host:5000/x, is kept)."""
    partes = imagem.partition("@")[0].rsplit("/", 1)
    partes[-1] = partes[-1].partition(":")[0]
    return "/".join(partes)


IMAGENS = list(_imagens())


def test_finds_the_system_images():
    """The scan sees the system image and production's database and Caddy (the docs site's
    Dockerfile is not inside the system image, so it is not required)."""
    arquivos = {file for file, _imagem in IMAGENS}
    assert {"Dockerfile", "docker-compose.yml", "deploy/docker-compose.prod.yml"} <= arquivos
    producao = {_repositorio(i) for a, i in IMAGENS if a == "deploy/docker-compose.prod.yml"}
    assert {"postgres", "caddy"} <= producao


@pytest.mark.parametrize(("file", "imagem"), IMAGENS)
def test_base_image_pinned_by_digest(file, imagem):
    assert DIGEST.search(imagem), f"{file}: {imagem} needs @sha256:<digest> (decision 138)"


def test_same_image_in_the_compose_files():
    """Development and production run the same PostgreSQL. Only the Compose files are compared:
    Dependabot updates them in one pull request (the imagens-compose group), while the docs
    site's Caddy, in a Dockerfile, gets its own and may differ from production's for a while."""
    por_repositorio = {}
    for file, imagem in IMAGENS:
        if "compose" in Path(file).name:
            por_repositorio.setdefault(_repositorio(imagem), {})[file] = imagem
    divergentes = {r: a for r, a in por_repositorio.items() if len(set(a.values())) > 1}
    assert not divergentes, divergentes


def test_scripts_and_ci_use_no_loose_tag():
    """The scripts and workflows that start a base image (the restore tests, the lock
    generator, CI's PostgreSQL) read it, digest included, from the Dockerfile or the production
    Compose file, never by a bare tag such as postgres:16-alpine."""
    repositorios = "|".join(sorted({re.escape(_repositorio(i)) for _a, i in IMAGENS}))
    solta = re.compile(rf"(?<![\w/.-])(?:{repositorios}):[\w.${{}}-]+(?!\S*@sha256:)")
    achados = []
    for file in _arquivos("*.sh", "*.yml", "*.yaml"):
        if "compose" in file.name or file.name == "releases.yaml":
            continue
        for number, row in enumerate(file.read_text().splitlines(), 1):
            code = row.split(" #", 1)[0]
            if code.lstrip().startswith("#"):
                continue
            local = file.relative_to(RAIZ)
            achados += [f"{local}:{number}: {m[0]}" for m in solta.finditer(code)]
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
def test_reading_the_from_line(dockerfile, esperado):
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
def test_repository(imagem, repositorio):
    assert _repositorio(imagem) == repositorio
