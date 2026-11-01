"""The Python version has one source, .python-version (decision 127): the image's default, the
CI and pyproject.toml must agree with it, so production never runs a version CI did not test."""

import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def test_versao_do_python_em_um_lugar_so():
    versao = (RAIZ / ".python-version").read_text().strip()
    assert re.fullmatch(r"3\.\d+", versao)
    dockerfile = (RAIZ / "Dockerfile").read_text()
    assert f"ARG PYTHON_VERSION={versao}\n" in dockerfile
    assert "FROM python:${PYTHON_VERSION}-slim" in dockerfile
    arquivo_ci = RAIZ / ".github" / "workflows" / "ci.yml"
    if not arquivo_ci.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    ci = arquivo_ci.read_text()
    assert "python-version:" not in ci  # every job reads .python-version
    assert ci.count("python-version-file: .python-version") >= 2
    assert '--build-arg PYTHON_VERSION="$(cat .python-version)"' in ci
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    assert projeto["project"]["requires-python"] == f">={versao}"
    # Ruff may lag one version behind (its 3.14 support was still a preview), never ahead.
    alvo = projeto["tool"]["ruff"]["target-version"]
    assert int(alvo[3:]) <= int(versao.split(".")[1]), alvo
