"""The Python version has one source, .python-version (decision 127): the image, the CI, the
locks and pyproject.toml must agree with it, so production never runs a version CI did not
test."""

import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def test_versao_do_python_em_um_lugar_so():
    versao = (RAIZ / ".python-version").read_text().strip()
    assert re.fullmatch(r"3\.\d+", versao)
    dockerfile = (RAIZ / "Dockerfile").read_text()
    # The image's Python, pinned by digest (decision 138).
    imagem = rf"^FROM python:{re.escape(versao)}-slim@sha256:[0-9a-f]{{64}}$"
    assert re.search(imagem, dockerfile, re.M)
    # The locks are resolved for this same Python (decision 136).
    gerar_lock = (RAIZ / "deploy" / "gerar_lock.sh").read_text()
    assert 'VERSAO=$(cat "$RAIZ/.python-version")' in gerar_lock
    assert '"python:$VERSAO-slim"' in gerar_lock
    for lock in ("requirements.txt", "requirements-dev.txt", "deploy/pip-tools.txt"):
        assert f"pip-compile with Python {versao}\n" in (RAIZ / lock).read_text(), lock
    arquivo_ci = RAIZ / ".github" / "workflows" / "ci.yml"
    if not arquivo_ci.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    ci = arquivo_ci.read_text()
    assert "python-version:" not in ci  # every job reads .python-version
    assert ci.count("python-version-file: .python-version") >= 2
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    assert projeto["project"]["requires-python"] == f">={versao}"
    # Ruff may lag one version behind, never ahead: with py314 its formatter writes
    # "except A, B:" (PEP 758), which reads like Python 2, so it stays on py313 (decision 130).
    alvo = projeto["tool"]["ruff"]["target-version"]
    assert int(alvo[3:]) <= int(versao.split(".")[1]), alvo
