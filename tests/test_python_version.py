"""The Python version has one source, .python-version (decision 127): the image, the CI, the
locks and pyproject.toml must agree with it, so production never runs a version CI did not
test."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_python_version_in_one_place():
    version = (ROOT_DIR / ".python-version").read_text().strip()
    assert re.fullmatch(r"3\.\d+", version)
    dockerfile = (ROOT_DIR / "Dockerfile").read_text()
    # The image's Python, pinned by digest (decision 138).
    image = rf"^FROM python:{re.escape(version)}-slim@sha256:[0-9a-f]{{64}}$"
    assert re.search(image, dockerfile, re.M)
    # The locks are resolved on this same image, digest included (decisions 136 and 138).
    lock_script = (ROOT_DIR / "deploy" / "lock.sh").read_text()
    assert re.search(r'^IMAGE=\$\(sed .*\(python:.* "\$ROOT/Dockerfile"\)$', lock_script, re.M)
    assert '-w /w "$IMAGE" sh -ec' in lock_script
    for lock in ("requirements.txt", "requirements-dev.txt", "deploy/pip-tools.txt"):
        assert f"pip-compile with Python {version}\n" in (ROOT_DIR / lock).read_text(), lock
    ci_file = ROOT_DIR / ".github" / "workflows" / "ci.yml"
    if not ci_file.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    ci = ci_file.read_text()
    assert "python-version:" not in ci  # every job reads .python-version
    assert ci.count("python-version-file: .python-version") >= 2
    project = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == f">={version}"
    # Ruff may lag one version behind, never ahead: with py314 its formatter writes
    # "except A, B:" (PEP 758), which reads like Python 2, so it stays on py313 (decision 130).
    target = project["tool"]["ruff"]["target-version"]
    assert int(target[3:]) <= int(version.split(".")[1]), target
