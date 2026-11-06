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

ROOT_DIR = Path(__file__).resolve().parent.parent
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
OUTSIDE = {".git", "node_modules", ".venv", "venv", "build", ".docusaurus"}


def _files(*defaults):
    seen_ones = set()
    for default in defaults:
        for file in sorted(ROOT_DIR.rglob(default)):
            if file not in seen_ones and not OUTSIDE.intersection(file.relative_to(ROOT_DIR).parts):
                seen_ones.add(file)
                yield file


def _dockerfile_from(text):
    """Images of the FROM lines: any case, continued lines joined, --platform and other flags
    skipped, and earlier stages (FROM build) and scratch left out."""
    stages = {"scratch"}
    for instruction in re.sub(r"\\\n", " ", text).splitlines():
        parts = instruction.split()
        if not parts or parts[0].upper() != "FROM":
            continue
        rest = [p for p in parts[1:] if not p.startswith("--")]
        if len(rest) >= 3 and rest[1].upper() == "AS":
            stages.add(rest[2].lower())
        if rest and rest[0].lower() not in stages:
            yield rest[0]


def _compose_images(text):
    services = (yaml.safe_load(text) or {}).get("services") or {}
    for service in services.values():
        image = str((service or {}).get("image") or "")
        if image and not image.startswith("${"):
            yield image


def _images():
    for file in _files("Dockerfile", "*.Dockerfile", "Dockerfile.*"):
        for image in _dockerfile_from(file.read_text()):
            yield file.relative_to(ROOT_DIR).as_posix(), image
    for file in _files("docker-compose*.yml", "docker-compose*.yaml", "compose*.y*ml"):
        for image in _compose_images(file.read_text()):
            yield file.relative_to(ROOT_DIR).as_posix(), image


def _repository(image):
    """postgres:16-alpine@sha256:… -> postgres (a registry port, as in host:5000/x, is kept)."""
    parts = image.partition("@")[0].rsplit("/", 1)
    parts[-1] = parts[-1].partition(":")[0]
    return "/".join(parts)


IMAGES = list(_images())


def test_finds_the_system_images():
    """The scan sees the system image and production's database and Caddy (the docs site's
    Dockerfile is not inside the system image, so it is not required)."""
    files = {file for file, _image in IMAGES}
    assert {"Dockerfile", "docker-compose.yml", "deploy/docker-compose.prod.yml"} <= files
    production = {_repository(i) for a, i in IMAGES if a == "deploy/docker-compose.prod.yml"}
    assert {"postgres", "caddy"} <= production


@pytest.mark.parametrize(("file", "image"), IMAGES)
def test_base_image_pinned_by_digest(file, image):
    assert DIGEST.search(image), f"{file}: {image} needs @sha256:<digest> (decision 138)"


def test_same_image_in_the_compose_files():
    """Development and production run the same PostgreSQL. Only the Compose files are compared:
    Dependabot updates them in one pull request (the imagens-compose group), while the docs
    site's Caddy, in a Dockerfile, gets its own and may differ from production's for a while."""
    by_repository = {}
    for file, image in IMAGES:
        if "compose" in Path(file).name:
            by_repository.setdefault(_repository(image), {})[file] = image
    divergent = {r: a for r, a in by_repository.items() if len(set(a.values())) > 1}
    assert not divergent, divergent


def test_scripts_and_ci_use_no_loose_tag():
    """The scripts and workflows that start a base image (the restore tests, the lock
    generator, CI's PostgreSQL) read it, digest included, from the Dockerfile or the production
    Compose file, never by a bare tag such as postgres:16-alpine."""
    repositories = "|".join(sorted({re.escape(_repository(i)) for _a, i in IMAGES}))
    loose = re.compile(rf"(?<![\w/.-])(?:{repositories}):[\w.${{}}-]+(?!\S*@sha256:)")
    found_items = []
    for file in _files("*.sh", "*.yml", "*.yaml"):
        if "compose" in file.name or file.name == "releases.yaml":
            continue
        for number, row in enumerate(file.read_text().splitlines(), 1):
            code = row.split(" #", 1)[0]
            if code.lstrip().startswith("#"):
                continue
            local = file.relative_to(ROOT_DIR)
            found_items += [f"{local}:{number}: {m[0]}" for m in loose.finditer(code)]
    assert not found_items, found_items


@pytest.mark.parametrize(
    ("dockerfile", "expected"),
    [
        ("FROM python:3@sha256:a\n", ["python:3@sha256:a"]),
        ("from node:26 AS build\nFROM build\n", ["node:26"]),
        ("FROM --platform=$BUILDPLATFORM node:26 AS b\nFROM caddy:2\n", ["node:26", "caddy:2"]),
        ("FROM \\\n  caddy:2\nRUN x\n", ["caddy:2"]),
        ("FROM scratch\n# FROM nada:1\n", []),
    ],
)
def test_reading_the_from_line(dockerfile, expected):
    assert list(_dockerfile_from(dockerfile)) == expected


@pytest.mark.parametrize(
    ("image", "repository"),
    [
        ("postgres:16-alpine@sha256:abc", "postgres"),
        ("caddy", "caddy"),
        ("registro:5000/eu/app:1", "registro:5000/eu/app"),
        ("ghcr.io/x/y@sha256:abc", "ghcr.io/x/y"),
    ],
)
def test_repository(image, repository):
    assert _repository(image) == repository
