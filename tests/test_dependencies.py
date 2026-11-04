"""The dependency locks (decision 136): every library chosen in a .in file is in its lock at the
same version, and the libraries both locks share have the same version and hashes, so the
tests in CI (requirements-dev.txt) run what the production image installs (requirements.txt).
CI also regenerates the locks and fails on any difference (deploy/lock.sh --check);
these checks need no network and catch the common mistakes earlier."""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PINO = re.compile(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([^\s\\;]+)")


def _nome(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _escolhidas(file):
    """Pins of a .in file (name -> version); -r/-c lines are followed by the lock itself."""
    pinos = {}
    for linha in (RAIZ / file).read_text().splitlines():
        if m := PINO.match(linha.strip()):
            pinos[_nome(m[1])] = m[2]
    return pinos


def _lock(file):
    """Packages of a lock: name -> (version, sorted hashes)."""
    pacotes, atual = {}, None
    for linha in (RAIZ / file).read_text().splitlines():
        if m := PINO.match(linha):
            atual = _nome(m[1])
            pacotes[atual] = (m[2], [])
        elif atual and (h := re.search(r"--hash=(\S+)", linha)):
            pacotes[atual][1].append(h[1])
    return {name: (versao, sorted(hashes)) for name, (versao, hashes) in pacotes.items()}


@pytest.mark.parametrize(
    "entrada,lock",
    [
        ("requirements.in", "requirements.txt"),
        ("requirements-dev.in", "requirements-dev.txt"),
        ("deploy/pip-tools.in", "deploy/pip-tools.txt"),
    ],
)
def test_lock_tem_as_versoes_do_in(entrada, lock):
    pacotes = _lock(lock)
    escolhidas = _escolhidas(entrada)
    assert escolhidas
    for name, versao in escolhidas.items():
        assert name in pacotes, f"{name} not in {lock}: run deploy/lock.sh"
        no_lock = pacotes[name][0]
        assert no_lock == versao, f"{name}: {entrada} has {versao}, {lock} has {no_lock}"
    assert all(hashes for _, hashes in pacotes.values()), f"{lock} has a package without a hash"


def test_locks_de_producao_e_de_desenvolvimento_concordam():
    producao = _lock("requirements.txt")
    desenvolvimento = _lock("requirements-dev.txt")
    assert producao.keys() <= desenvolvimento.keys(), "production packages missing in the dev lock"
    diferentes = [name for name, pino in producao.items() if desenvolvimento[name] != pino]
    assert not diferentes, f"version or hashes differ between the locks: {diferentes}"


def test_ci_confere_os_locks():
    arquivo_ci = RAIZ / ".github" / "workflows" / "ci.yml"
    if not arquivo_ci.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    assert "deploy/lock.sh --check" in arquivo_ci.read_text()


def test_lint_a_cada_commit_usa_o_ruff_do_lock():
    """Decision 137: the Lint workflow runs on every push and installs ruff from the lock,
    with its hashes, for the Python of .python-version."""
    file = RAIZ / ".github" / "workflows" / "lint.yml"
    if not file.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    lint = file.read_text()
    assert "\n  push:\n" in lint
    assert "python-version-file: .python-version" in lint and "python-version:" not in lint
    assert "requirements-dev.txt" in lint and "--require-hashes" in lint
    assert "ruff check" in lint and "ruff format --check" in lint
