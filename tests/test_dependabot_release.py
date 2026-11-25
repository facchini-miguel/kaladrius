"""Decision 219: the version of what Dependabot brought (.github/dependabot_release.py, run by
.github/workflows/dependabot-release.yml after every push to main). The tests build a small
repository with the project's own pyproject.toml, READMEs and releases.yaml, merge pull requests
into it the way GitHub does, and read what the script writes with the project's own reader of
releases.yaml (the one What's new and CI use)."""

import datetime
import importlib.util
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from apps.whats_new import releases

ROOT_DIR = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "dependabot_release", ROOT_DIR / ".github" / "dependabot_release.py"
)
release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release)

DAY = datetime.date(2026, 11, 25)
GROUP = "Bump the python-menores group across 1 directory with 3 updates"
GROUP_BODY = """Bumps the python-menores group with 3 updates in the / directory:

| Package | From | To |
| --- | --- | --- |
| [psycopg](https://github.com/psycopg/psycopg) | `3.3.8` | `3.3.9` |
| [pyotp](https://github.com/pyauth/pyotp) | `2.10.0` | `2.12.0` |
| [coverage](https://github.com/coveragepy/coveragepy) | `7.17.2` | `7.17.3` |


Updates `psycopg` from 3.3.8 to 3.3.9
<details><summary>Release notes</summary>...</details>
"""
REQUIREMENTS = """psycopg==3.3.8 \\
    --hash=sha256:aaaa
pyotp==2.10.0 \\
    --hash=sha256:bbbb
gunicorn==26.2.0 \\
    --hash=sha256:cccc
"""
DEV = "-r requirements.txt\ncoverage==7.17.2\nruff==0.17.4\n"


class Repository:
    """A git repository with the project's version files, where pull requests get merged.

    Its releases.yaml is the project's, which names real pull requests (#110 and #111 since
    0.72.4), and a named one is left alone: the tests merge numbers far above the real ones
    (9xxxx), except the one that checks exactly that (#107)."""

    def __init__(self, path):
        self.path = path
        self.pulls = {}
        for name in ["pyproject.toml", "releases.yaml", *release.READMES]:
            shutil.copy(ROOT_DIR / name, path / name)
        (path / "requirements.txt").write_text(REQUIREMENTS)
        (path / "requirements-dev.txt").write_text(DEV)
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Release")
        self.git("tag", "v0.0.0")

    def git(self, *args):
        return subprocess.run(  # noqa: S603 (git with the test's own arguments)
            [shutil.which("git"), "-c", "user.name=Test", "-c", "user.email=t@example.com", *args],
            cwd=self.path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def merge(self, number, files, title="", body="", login=release.DEPENDABOT, branch=None):
        """A pull request with these files (name: new content, or a function of the old one)."""
        branch = branch or f"dependabot/pip/pr-{number}"
        self.git("switch", "-q", "-c", branch, "main")
        for name, content in files.items():
            path = self.path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            old = path.read_text() if path.exists() else ""
            path.write_text(content(old) if callable(content) else content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", title or f"Change {number}")
        self.git("switch", "-q", "main")
        message = f"Merge pull request #{number} from owner/{branch}"
        self.git("merge", "-q", "--no-ff", "-m", message, branch)
        self.pulls[number] = {"login": login, "title": title, "body": body}

    def pending(self):
        return release.pending(self.path, "v0.0.0", fetch=self.pulls.__getitem__)

    def version(self):
        return tomllib.loads((self.path / "pyproject.toml").read_text())["project"]["version"]

    def write(self):
        """What the workflow does: the script's files, committed on its branch and merged."""
        pulls = self.pending()
        version = release.next_version(self.version())
        release.write(self.path, version, DAY, pulls)
        return version, pulls


def bump(old, new):
    return lambda text: text.replace(old, new)


@pytest.fixture
def repository(tmp_path):
    return Repository(tmp_path)


def test_updates_named_by_a_group_and_by_a_title():
    assert release.updates_of(GROUP, GROUP_BODY) == [
        release.Update("psycopg", "3.3.8", "3.3.9"),
        release.Update("pyotp", "2.10.0", "2.12.0"),
        release.Update("coverage", "7.17.2", "7.17.3"),
    ]
    assert release.updates_of("Bump gunicorn from 26.2.0 to 27.0.1", "") == [
        release.Update("gunicorn", "26.2.0", "27.0.1")
    ]
    docs = release.updates_of("Bump node from 26-alpine to 27-alpine in /docs", "")
    assert [update.text() for update in docs] == ["node 26-alpine → 27-alpine"]
    digest = release.updates_of("Bump python from `cd89c30` to `0a1b2c3`", "")
    assert [update.text() for update in digest] == ["python"], "a new build: only its name"


def test_only_names_and_versions_of_the_body_reach_releases_yaml():
    body = (
        "| [two words](x) | `1.0` | `2.0` |\n"
        "| [ok](x) | `1.0` | `2.0: injected` |\n"
        "| [@docusaurus/core](x) | `3.9.1` | `3.9.2` |\n"
    )
    assert release.updates_of("Bump the docs group", body) == [
        release.Update("@docusaurus/core", "3.9.1", "3.9.2")
    ]


def test_the_merged_dependabot_pull_requests_get_the_next_version(repository):
    repository.merge(
        90110,
        {
            "requirements.txt": bump("psycopg==3.3.8", "psycopg==3.3.9"),
            "requirements-dev.txt": bump("coverage==7.17.2", "coverage==7.17.3"),
        },
        GROUP,
        GROUP_BODY,
    )
    repository.merge(
        90111,
        {"requirements.txt": bump("gunicorn==26.2.0", "gunicorn==27.0.1")},
        "Bump gunicorn from 26.2.0 to 27.0.1",
    )
    # Not shipped: the workflows, the development tools; not Dependabot's: the owner's.
    repository.merge(
        90112,
        {".github/workflows/ci.yml": "x"},
        "Bump the acoes group",
        branch="dependabot/github_actions/acoes",
    )
    repository.merge(
        90113,
        {"requirements-dev.txt": bump("ruff==0.17.4", "ruff==0.17.5")},
        "Bump ruff from 0.17.4 to 0.17.5",
    )
    repository.merge(90114, {"apps/x.py": "x = 1\n"}, "A change", login="facchini-miguel")

    current = repository.version()
    version, pulls = repository.write()
    assert [pull.number for pull in pulls] == [90110, 90111]
    assert version == release.next_version(current)
    newest = releases.read_releases(repository.path / "releases.yaml")[0]
    assert newest.version == version and newest.date == DAY
    assert [(item.source, item.pr, item.kind, item.module) for item in newest.items] == [
        ("dependabot", 90110, "improvement", "System"),
        ("dependabot", 90111, "improvement", "System"),
    ]
    texts = dict(newest.items[0].texts)
    assert set(texts) == {"pt-br", "en", "es"}, "a test of the project requires the three"
    # coverage is in the group, but only requirements-dev.txt has it: not in the image.
    assert " ".join(texts["en"].split()) == (
        "System libraries updated: psycopg 3.3.8 → 3.3.9. Nothing changes for users."
    )
    assert "gunicorn 26.2.0 → 27.0.1" in dict(newest.items[1].texts)["pt-br"]
    assert repository.version() == version
    for name, label in release.READMES.items():
        assert f"{label}{version}" in (repository.path / name).read_text()


def test_after_its_version_is_merged_nothing_is_pending(repository):
    repository.merge(
        90111,
        {"requirements.txt": bump("gunicorn==26.2.0", "gunicorn==27.0.1")},
        "Bump gunicorn from 26.2.0 to 27.0.1",
    )
    version, _ = repository.write()
    repository.git("switch", "-q", "-c", "versao-bibliotecas")
    repository.git("commit", "-q", "-am", f"Release {version}")
    repository.git("switch", "-q", "main")
    repository.git(
        "merge",
        "-q",
        "--no-ff",
        "-m",
        "Merge pull request #90115 from owner/versao-bibliotecas",
        "versao-bibliotecas",
    )
    assert repository.pending() == []

    repository.merge(
        90116,
        {"requirements.txt": bump("pyotp==2.10.0", "pyotp==2.12.0")},
        "Bump pyotp from 2.10.0 to 2.12.0",
    )
    assert [pull.number for pull in repository.pending()] == [90116]
    assert release.next_version(repository.version()) == release.next_version(version)


def test_a_version_written_by_hand_covers_what_came_before_it(repository):
    repository.merge(
        90110, {"requirements.txt": bump("psycopg==3.3.8", "psycopg==3.3.9")}, GROUP, GROUP_BODY
    )
    current = repository.version()
    repository.merge(
        90117,
        {"pyproject.toml": bump(f'version = "{current}"', 'version = "9.0.0"')},
        "Release 9.0.0",
        login="facchini-miguel",
        branch="nova-versao",
    )
    assert repository.pending() == [], "#90110 went out in 9.0.0"


def test_already_in_releases_yaml_is_left_alone(repository):
    repository.merge(
        107, {"requirements.txt": bump("psycopg==3.3.8", "psycopg==3.3.9")}, GROUP, GROUP_BODY
    )
    assert repository.pending() == [], "0.72.2 names #107"


def test_documentation_security_and_long_lists(repository):
    rows = "".join(f"| [lib{n}](x) | `1.{n}` | `2.{n}` |\n" for n in range(8))
    repository.merge(
        90120,
        {"docs/package-lock.json": "{}"},
        "Bump the documentacao-menores group",
        rows + "\nFixes CVE-2026-12345.",
        branch="dependabot/npm_and_yarn/docs/x",
    )
    version, pulls = repository.write()
    item = releases.read_releases(repository.path / "releases.yaml")[0].items[0]
    assert (item.kind, item.module) == ("security", "Documentation")
    texts = {language: " ".join(text.split()) for language, text in item.texts}
    assert texts["pt-br"].startswith(
        "Bibliotecas do site de documentação atualizadas: lib0 1.0 → 2.0"
    )
    assert texts["pt-br"].endswith("lib5 1.5 → 2.5, e mais 2. O conteúdo não muda.")
    assert "and 2 more" in texts["en"] and "y 2 más" in texts["es"]
    lines = (repository.path / "releases.yaml").read_text().splitlines()
    assert all(len(line) <= 100 for line in lines)


def test_the_pull_request_title_and_body():
    pulls = [
        release.Pull(110, GROUP, (release.Update("psycopg", "3.3.8", "3.3.9"),), False, False),
        release.Pull(111, "Bump gunicorn | x", (), False, False),
    ]
    title, body = release.summary("0.72.4", pulls)
    assert title == "Release 0.72.4: libraries updated (Dependabot #110, #111)"
    assert "| #110 | " + GROUP + " | psycopg 3.3.8 → 3.3.9 |" in body
    assert "| #111 | Bump gunicorn / x | - |" in body, "a | of a title does not break the table"
    assert body.rstrip().endswith("<!-- dependabot-release: 110,111 -->"), "the workflow's marker"


def test_the_repository_releases_yaml_names_the_dependabot_pull_requests():
    text = (ROOT_DIR / "releases.yaml").read_text()
    listed = {int(number) for number in release.LISTED.findall(text)}
    named = {
        item.pr
        for version in releases.read_releases(ROOT_DIR / "releases.yaml")
        for item in version.items
        if item.pr
    }
    assert listed == named and 107 in listed


def _workflow(name):
    data = yaml.safe_load((ROOT_DIR / ".github" / "workflows" / name).read_text())
    return data, data.get("on", data.get(True))  # PyYAML reads the "on" key as True


def test_the_workflow_starts_the_checks_of_its_pull_request():
    data, on = _workflow("dependabot-release.yml")
    assert on["push"] == {"branches": ["main"]}
    text = (ROOT_DIR / ".github" / "workflows" / "dependabot-release.yml").read_text()
    assert all(
        re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
        for step in data["jobs"]["release"]["steps"]
        if "uses" in step
    )
    started = re.search(r"for workflow in ([^;]+); do", text)[1].split()
    assert started == ["ci.yml", "image-age.yml", "lint.yml"]
    for name in started:
        assert "workflow_dispatch" in _workflow(name)[1], f"{name} can be started on the branch"
    start = data["env"]["START"]
    assert start.startswith("v") and start[1:] in {
        version.version for version in releases.read_releases(ROOT_DIR / "releases.yaml")
    }
