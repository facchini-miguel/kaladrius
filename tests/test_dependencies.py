"""The dependency locks (decision 136): every library chosen in a .in file is in its lock at the
same version, and the libraries both locks share have the same version and hashes, so the
tests in CI (requirements-dev.txt) run what the production image installs (requirements.txt).
CI also regenerates the locks and fails on any difference (deploy/lock.sh --check);
these checks need no network and catch the common mistakes earlier."""

import re
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([^\s\\;]+)")


def _name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _chosen(file):
    """Pins of a .in file (name -> version); -r/-c lines are followed by the lock itself."""
    pins = {}
    for row in (ROOT_DIR / file).read_text().splitlines():
        if m := PIN.match(row.strip()):
            pins[_name(m[1])] = m[2]
    return pins


def _lock(file):
    """Packages of a lock: name -> (version, sorted hashes)."""
    packages, current = {}, None
    for row in (ROOT_DIR / file).read_text().splitlines():
        if m := PIN.match(row):
            current = _name(m[1])
            packages[current] = (m[2], [])
        elif current and (h := re.search(r"--hash=(\S+)", row)):
            packages[current][1].append(h[1])
    return {name: (version, sorted(hashes)) for name, (version, hashes) in packages.items()}


@pytest.mark.parametrize(
    "entry_line,lock",
    [
        ("requirements.in", "requirements.txt"),
        ("requirements-dev.in", "requirements-dev.txt"),
        ("deploy/pip-tools.in", "deploy/pip-tools.txt"),
    ],
)
def test_lock_has_the_versions_of_the_in_file(entry_line, lock):
    packages = _lock(lock)
    chosen = _chosen(entry_line)
    assert chosen
    for name, version in chosen.items():
        assert name in packages, f"{name} not in {lock}: run deploy/lock.sh"
        no_lock = packages[name][0]
        assert no_lock == version, f"{name}: {entry_line} has {version}, {lock} has {no_lock}"
    assert all(hashes for _, hashes in packages.values()), f"{lock} has a package without a hash"


def test_production_and_development_locks_agree():
    production = _lock("requirements.txt")
    development = _lock("requirements-dev.txt")
    assert production.keys() <= development.keys(), "production packages missing in the dev lock"
    different = [name for name, pin in production.items() if development[name] != pin]
    assert not different, f"version or hashes differ between the locks: {different}"


def test_ci_checks_the_locks():
    ci_file = ROOT_DIR / ".github" / "workflows" / "ci.yml"
    if not ci_file.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    assert "deploy/lock.sh --check" in ci_file.read_text()


def test_commit_lint_uses_the_locked_ruff():
    """Decision 137: the Lint workflow runs on every push and installs ruff from the lock,
    with its hashes, for the Python of .python-version."""
    file = ROOT_DIR / ".github" / "workflows" / "lint.yml"
    if not file.exists():  # inside the image, which leaves .github out
        pytest.skip(".github is not in the image")
    lint = file.read_text()
    assert "\n  push:\n" in lint
    assert "python-version-file: .python-version" in lint and "python-version:" not in lint
    assert "requirements-dev.txt" in lint and "--require-hashes" in lint
    assert "ruff check" in lint and "ruff format --check" in lint
