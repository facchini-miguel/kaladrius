"""The version of what Dependabot brought (decision 219).

Run by .github/workflows/dependabot-release.yml after every push to main. It looks at the
Dependabot pull requests merged into main (its first-parent history) after the last version
change and after <start>, that change what is shipped (the app image, the Linux packages, the
documentation site) and that releases.yaml does not name yet. When there are any, it writes
their version, the next PATCH: pyproject.toml, the "Current version" line of the three READMEs
and an entry at the top of releases.yaml, one item per pull request (source: dependabot, its
pr), in the three languages. The workflow then opens or updates that version's pull request.

    python3 .github/dependabot_release.py <start> <out dir>

<out dir> gets title.txt and body.md (the pull request's) when there is a version to write;
nothing is written when there is none. Standard library only (the runner's python3); the pull
requests are read with the gh CLI.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DEPENDABOT = "dependabot[bot]"
# What a Dependabot pull request may change without changing what is shipped: the workflows,
# the development and lock tools, the development Compose. The image installs requirements.txt
# (Dockerfile), the Linux packages carry deploy/docker-compose.prod.yml, the documentation site
# is built from docs/.
NOT_SHIPPED = re.compile(
    r"\.github/.*|requirements-dev\.(in|txt)|deploy/pip-tools\.(in|txt)|docker-compose\.yml"
)
MERGE = re.compile(r"Merge pull request #(\d+) from \S+")
SQUASH = re.compile(r".* \(#(\d+)\)")
# Dependabot's table of a group (| [name](url) | `from` | `to` |) and its title for one package.
TABLE_ROW = re.compile(
    r"^\|\s*\[?([^\]|(]+?)\]?(?:\([^)]*\))?\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE
)
TITLE = re.compile(r"Bump (\S+) from (\S+) to (\S+)(?: in \S+)?")
# What goes into releases.yaml: package names and versions only, nothing else of the body.
NAME = re.compile(r"@?[A-Za-z0-9][A-Za-z0-9._/\[\]-]*")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
DIGEST = re.compile(r"[0-9a-f]{7,64}")
PIN = re.compile(r"^[+-]([A-Za-z0-9][A-Za-z0-9._-]*)==", re.MULTILINE)
SECURITY = re.compile(r"\b(CVE-\d{4}-\d{4,}|GHSA(-[0-9a-z]{4}){3})\b", re.IGNORECASE)
LISTED = re.compile(r"^\s+pr:\s*(\d+)\s*$", re.MULTILINE)
SHOWN = 6  # updates named in an item; the rest are counted
ZONE = ZoneInfo("America/Sao_Paulo")
READMES = {
    "README.md": "Current version: ",
    "README.pt-BR.md": "Versão atual: ",
    "README.es.md": "Versión actual: ",
}
TITLES = {
    "pt-br": "Bibliotecas atualizadas",
    "en": "Libraries updated",
    "es": "Bibliotecas actualizadas",
}
# (start, end) of an item's text, for the system and for the documentation site.
SYSTEM = {
    "pt-br": ("Bibliotecas do sistema atualizadas", "Nada muda para quem usa o sistema."),
    "en": ("System libraries updated", "Nothing changes for users."),
    "es": ("Bibliotecas del sistema actualizadas", "Nada cambia para quien usa el sistema."),
}
DOCS = {
    "pt-br": ("Bibliotecas do site de documentação atualizadas", "O conteúdo não muda."),
    "en": ("Documentation site libraries updated", "Its content does not change."),
    "es": ("Bibliotecas del sitio de documentación actualizadas", "El contenido no cambia."),
}
MORE = {"pt-br": "e mais {}", "en": "and {} more", "es": "y {} más"}


@dataclass(frozen=True)
class Update:
    name: str
    old: str
    new: str

    def text(self):
        if DIGEST.fullmatch(self.old) and DIGEST.fullmatch(self.new):
            return self.name  # a new build of the same tag: only its digest changed
        return f"{self.name} {self.old} → {self.new}"


@dataclass(frozen=True)
class Pull:
    number: int
    title: str
    updates: tuple[Update, ...]
    docs: bool  # only the documentation site changes
    security: bool

    def text(self, language):
        start, end = (DOCS if self.docs else SYSTEM)[language]
        names = [update.text() for update in self.updates[:SHOWN]]
        if len(self.updates) > SHOWN:
            names.append(MORE[language].format(len(self.updates) - SHOWN))
        return f"{start}: {', '.join(names)}. {end}" if names else f"{start}. {end}"


def git(root, *args):
    return subprocess.run(  # noqa: S603 (git with the script's own arguments)
        [shutil.which("git"), *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def pull_request(number):
    """The pull request from GitHub: who opened it, its title and its body."""
    repository = os.environ["GITHUB_REPOSITORY"]
    out = subprocess.run(  # noqa: S603 (gh with the script's own arguments)
        [
            shutil.which("gh"),
            "api",
            f"repos/{repository}/pulls/{number}",
            "--jq",
            '{login: .user.login, title: .title, body: (.body // "")}',
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def merged(root, start):
    """(commit, number) of each pull request merged into main after start and after the last
    version change, oldest first."""
    commits = git(root, "log", "--first-parent", "--reverse", "--format=%H %s", f"{start}..HEAD")
    bumps = set(
        git(
            root,
            "log",
            "--first-parent",
            "--format=%H",
            "-G",
            "^version = ",
            f"{start}..HEAD",
            "--",
            "pyproject.toml",
        ).split()
    )
    found = []
    for line in commits.splitlines():
        sha, _, subject = line.partition(" ")
        if sha in bumps:
            found = []  # what came before is in that version
            continue
        match = MERGE.fullmatch(subject) or SQUASH.fullmatch(subject)
        if match:
            found.append((sha, int(match[1])))
    return found


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def updates_of(title, body):
    """The updates a Dependabot pull request names: its table (a group) or its title."""
    rows = [tuple(cell.strip().strip("`") for cell in row) for row in TABLE_ROW.findall(body)]
    if not rows:
        match = TITLE.fullmatch(title.replace("`", "").strip())
        rows = [match.groups()[:3]] if match else []
    updates = []
    for name, old, new in rows:
        update = Update(name, old, new)
        valid = NAME.fullmatch(name) and VERSION.fullmatch(old) and VERSION.fullmatch(new)
        if valid and update not in updates:
            updates.append(update)
    return updates


def pending(root, start, fetch=pull_request):
    """The Dependabot pull requests that still need a version."""
    listed = {int(number) for number in LISTED.findall((root / "releases.yaml").read_text())}
    pulls = []
    for sha, number in merged(root, start):
        if number in listed:
            continue
        pr = fetch(number)
        if pr["login"] != DEPENDABOT:
            continue
        files = git(root, "diff", "--name-only", f"{sha}^1", sha).split()
        shipped = [file for file in files if not NOT_SHIPPED.fullmatch(file)]
        if not shipped:
            continue
        updates = updates_of(pr["title"], pr["body"])
        if "requirements.txt" in files:
            # Only the libraries the image installs, not the development ones of the group.
            diff = git(root, "diff", f"{sha}^1", sha, "--", "requirements.txt")
            pins = {normalized(name) for name in PIN.findall(diff)}
            updates = [update for update in updates if normalized(update.name) in pins] or updates
        pulls.append(
            Pull(
                number=number,
                title=pr["title"],
                updates=tuple(updates),
                docs=all(file.startswith("docs/") for file in shipped),
                security=bool(SECURITY.search(pr["body"])),
            )
        )
    return pulls


def next_version(version):
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def folded(text):
    """A text of releases.yaml: a folded block, 100 columns."""
    return textwrap.fill(
        text,
        width=100,
        initial_indent=" " * 10,
        subsequent_indent=" " * 10,
        break_long_words=False,
        break_on_hyphens=False,
    )


def entry(version, date, pulls):
    lines = [
        f"- version: {version}",
        f"  date: {date.isoformat()}",
        "  title:",
        *(f"    {language}: {text}" for language, text in TITLES.items()),
        "  items:",
    ]
    for pull in pulls:
        lines += [
            f"    - kind: {'security' if pull.security else 'improvement'}",
            f"      module: {'Documentation' if pull.docs else 'System'}",
            "      audience: [staff]",
            "      source: dependabot",
            f"      pr: {pull.number}",
            "      text:",
        ]
        for language in TITLES:
            lines += [f"        {language}: >", folded(pull.text(language))]
    return "\n".join(lines) + "\n"


def replace_once(text, pattern, new, file):
    text, count = re.subn(pattern, new, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{file}: no line to change ({pattern})")
    return text


def write(root, version, date, pulls):
    """The new version in pyproject.toml, the READMEs and at the top of releases.yaml."""
    path = root / "pyproject.toml"
    text = replace_once(path.read_text(), r'^version = "[^"]*"', f'version = "{version}"', path)
    path.write_text(text)
    for name, label in READMES.items():
        path = root / name
        number = rf"{re.escape(label)}\d+\.\d+\.\d+"
        path.write_text(replace_once(path.read_text(), number, label + version, path))
    path = root / "releases.yaml"
    text = path.read_text()
    first = re.search(r"^- version:", text, flags=re.MULTILINE)
    if not first:
        raise SystemExit(f"{path}: no version")
    at = first.start()
    path.write_text(text[:at] + entry(version, date, pulls) + "\n" + text[at:])


def summary(version, pulls):
    """(title, body) of the version's pull request."""
    numbers = ", ".join(f"#{pull.number}" for pull in pulls)
    title = f"Release {version}: libraries updated (Dependabot {numbers})"
    rows = "\n".join(
        f"| #{pull.number} | {pull.title.replace('|', '/')} | "
        f"{', '.join(update.text() for update in pull.updates) or '-'} |"
        for pull in pulls
    )
    body = f"""Version **{version}** for the Dependabot pull requests merged since the last \
version, written by the Dependabot release workflow (`.github/workflows/dependabot-release.yml`, \
decision 219): `pyproject.toml`, the three READMEs and the top of `releases.yaml` (What's new).

| Pull request | Title | In the release notes |
|---|---|---|
{rows}

**Merging it publishes {version}:** CI tags `v{version}` and creates its GitHub release, and the \
reference server installs it within 5 minutes (it goes back by itself if the new version does not \
answer).

The branch belongs to the workflow: it writes it again from `main` when `main` changes (another \
Dependabot pull request merged first is added to this version), so do not commit to it. Closed \
without merging, it does not come back for the same pull requests.

<!-- dependabot-release: {",".join(str(pull.number) for pull in pulls)} -->
"""
    return title, body


def main(argv):
    start, out = argv[1], Path(argv[2])
    pulls = pending(ROOT, start)
    if not pulls:
        print(f"No Dependabot pull request without a version since {start} and the last version.")
        return 0
    current = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    version = next_version(current)
    write(ROOT, version, datetime.datetime.now(ZONE).date(), pulls)
    title, body = summary(version, pulls)
    out.mkdir(parents=True, exist_ok=True)
    (out / "title.txt").write_text(title + "\n")
    (out / "body.md").write_text(body)
    print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
