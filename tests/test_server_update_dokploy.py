"""The reference production's update on the VPS, with the version (decision 217):
deploy/server/update-dokploy.sh run with a fake `curl` (Dokploy's API, GitHub's newest release
and the system's health page) and a fake `docker`, and the helpers of common.sh replaced, so no
container, registry or network is touched. The Compose lives in a file the fake Dokploy reads
and writes; each deploy "runs" the version its app line names, which the health page answers."""

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
UPDATE = ROOT_DIR / "deploy" / "server" / "update-dokploy.sh"

pytestmark = pytest.mark.skipif(not shutil.which("flock"), reason="needs flock (util-linux)")

COMPOSE = """services:
  db:
    image: postgres:16-alpine
  app:
    image: ghcr.io/facchini-miguel/kaladrius:{app}
    env_file: .env
  docs:
    build:
      context: https://github.com/facchini-miguel/kaladrius.git#{docs}:docs
"""

# Fake curl: the URL is the last argument; --data-binary @file is the body.
CURL = r"""#!/usr/bin/env python3
import json, os, re, sys
d = os.environ["FAKE"]
args = sys.argv[1:]
url = args[-1]
body = None
if "--data-binary" in args:
    body = json.load(open(args[args.index("--data-binary") + 1][1:]))
def log(line):
    open(f"{d}/log", "a").write(line + "\n")
def compose():
    return open(f"{d}/compose.yml").read()
if url.endswith("/releases/latest"):
    if os.path.exists(f"{d}/github-down"):
        sys.exit(22)
    print(json.dumps({"tag_name": "v" + open(f"{d}/newest").read().strip()}))
elif "/api/compose.one" in url:
    print(json.dumps({"composeFile": compose(), "composeStatus": open(f"{d}/status").read().strip(),
                      "env": "DJANGO_SECRET_KEY=secret"}))
elif url.endswith("/api/compose.update"):
    open(f"{d}/compose.yml", "w").write(body["composeFile"])
    app = re.search(r"kaladrius:(\S+)", body["composeFile"])[1]
    log(f"update {app}")
elif url.endswith("/api/compose.deploy"):
    app = re.search(r"kaladrius:(\S+)", compose())[1]
    broken = open(f"{d}/broken").read().split() if os.path.exists(f"{d}/broken") else []
    # The system that runs now: the Compose's version, unless it is broken (then it answers 503).
    open(f"{d}/running", "w").write("" if app in broken else app)
    log(f"deploy {app} ({body['title']})")
elif url.endswith("/api/v1/health"):
    running = open(f"{d}/running").read().strip()
    if not running:
        sys.exit(22)
    print(json.dumps({"database": True, "version": running}))
else:
    print(f"fake curl: {url}", file=sys.stderr)
    sys.exit(2)
"""

DOCKER = r"""#!/bin/bash
[ "$1 $2" = "pull -q" ] || { echo "fake docker: $*" >&2; exit 2; }
[ -f "$FAKE/pull-fails" ] && exit 1
echo "pull ${@: -1}" >> "$FAKE/log"
"""

COMMON = r"""
DIR="{dir}"
HEALTH_WAIT=0
log() {{ echo "$*" >> "$DIR/log"; }}
notify_monitor() {{ log "monitor $1 ${{2:-ok}}"; }}
begin_maintenance() {{ log "maintenance on"; }}
end_maintenance() {{ log "maintenance off"; }}
write_metrics() {{ log "metrics $1 $(grep -v '^#' | cut -d' ' -f1 | tr '\n' ' ')"; }}
site_curl_options() {{ CURL_OPTIONS=(--resolve "$1:443:127.0.0.1"); }}
"""


@pytest.fixture
def server(tmp_path):
    bin_ = tmp_path / "bin"
    path = tmp_path / "path"
    bin_.mkdir()
    path.mkdir()
    shutil.copy(UPDATE, bin_ / "update-dokploy.sh")
    (bin_ / "common.sh").write_text(textwrap.dedent(COMMON.format(dir=tmp_path)))
    for name, text in (("curl", CURL), ("docker", DOCKER)):
        (path / name).write_text(text)
        (path / name).chmod(0o755)
    (tmp_path / "compose-id").write_text("abc123\n")
    (tmp_path / "api-key").write_text("key\n")

    class Server:
        dir = tmp_path

        def compose(self, app, docs):
            (tmp_path / "compose.yml").write_text(COMPOSE.format(app=app, docs=docs))
            (tmp_path / "running").write_text(app if app[0].isdigit() else "0.72.2")

        def newest(self, version):
            (tmp_path / "newest").write_text(version + "\n")

        def broken(self, *versions):
            (tmp_path / "broken").write_text(" ".join(versions))

        def lines(self):
            text = (tmp_path / "compose.yml").read_text()
            return [ln.strip() for ln in text.splitlines() if "facchini-miguel/kaladrius" in ln]

        def state(self, name):
            file = tmp_path / "version" / name
            return file.read_text().strip() if file.exists() else None

        def run(self, *args):
            (tmp_path / "log").write_text("")
            environment = {
                # python3 (the script's helpers and the fake curl): the one running the tests.
                "PATH": f"{path}:{Path(sys.executable).parent}:/usr/bin:/bin",
                "FAKE": str(tmp_path),
                "COMPOSE_ID_FILE": str(tmp_path / "compose-id"),
                "KEY_FILE": str(tmp_path / "api-key"),
                "DEPLOY_INTERVAL": "0",
                "HEALTH_INTERVAL": "0",
            }
            result = subprocess.run(  # noqa: S603 (the test's own script and arguments)
                [shutil.which("bash"), str(bin_ / "update-dokploy.sh"), *args],
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
            log = (tmp_path / "log").read_text().splitlines()
            return result.returncode, log, result.stdout + result.stderr

    s = Server()
    (tmp_path / "status").write_text("done\n")
    s.compose("0.72.2", "v0.72.2")
    s.newest("0.72.2")
    return s


APP = "image: ghcr.io/facchini-miguel/kaladrius:{}"
DOCS = "context: https://github.com/facchini-miguel/kaladrius.git#v{}:docs"
MAIN = DOCS.replace("#v{}:", "#main:")


def test_on_the_newest_version_nothing_changes(server):
    code, log, _ = server.run()
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]


def test_the_first_run_puts_the_version_in_place_of_latest(server):
    """Before decision 217 the Compose named :latest and built the docs from main."""
    server.compose("latest", "main")
    code, log, out = server.run()
    assert code == 0, out
    assert server.lines() == [APP.format("0.72.2"), DOCS.format("0.72.2")]
    assert log == [
        "pull ghcr.io/facchini-miguel/kaladrius:0.72.2",
        "update 0.72.2",
        "maintenance on",
        "deploy 0.72.2 (Kaladrius 0.72.2)",
        "maintenance off",
        "metrics update kaladrius_update_last_success_timestamp_seconds ",
        "monitor MONITOR_UPDATE_URL ok",
    ]
    assert "latest -> 0.72.2" in out


def test_a_new_release_is_installed_and_only_the_two_lines_change(server):
    before = (server.dir / "compose.yml").read_text()
    server.newest("0.73.0")
    code, log, _ = server.run()
    assert code == 0
    after = (server.dir / "compose.yml").read_text()
    assert after == before.replace(":0.72.2", ":0.73.0").replace("#v0.72.2:", "#v0.73.0:")
    assert "deploy 0.73.0 (Kaladrius 0.73.0)" in log
    assert log[-1] == "monitor MONITOR_UPDATE_URL ok"
    assert server.state("compose-previous.yml") is not None


def test_a_version_that_does_not_come_up_goes_back_and_is_refused(server):
    server.newest("0.73.0")
    server.broken("0.73.0")
    code, log, out = server.run()
    assert code == 1
    assert server.lines() == [APP.format("0.72.2"), DOCS.format("0.72.2")], "the previous Compose"
    assert log == [
        "pull ghcr.io/facchini-miguel/kaladrius:0.73.0",
        "update 0.73.0",
        "maintenance on",
        "deploy 0.73.0 (Kaladrius 0.73.0)",
        "update 0.72.2",
        "deploy 0.72.2 (Back: 0.73.0 did not come up)",
        "monitor MONITOR_UPDATE_URL fail",
        "maintenance off",
    ]
    assert server.state("refused") == "0.73.0"
    assert "Back on 0.72.2" in out

    code, log, out = server.run()  # the next run: refused, nothing touched, still a failure
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL fail"]
    assert "refused" in out

    server.newest("0.73.1")  # a newer one is tried, and its success forgets the refusal
    code, log, _ = server.run()
    assert code == 0
    assert server.lines()[0] == APP.format("0.73.1")
    assert server.state("refused") is None


def test_never_down_by_itself(server):
    server.compose("0.73.0", "v0.73.0")
    server.newest("0.72.2")  # a release deleted, or the newest one changed by hand
    code, log, out = server.run()
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]
    assert server.lines()[0] == APP.format("0.73.0")
    assert "never down by itself" in out


def test_a_version_by_hand_is_installed_and_held_until_release(server):
    server.compose("0.73.0", "v0.73.0")
    server.newest("0.73.0")
    code, log, out = server.run("0.72.2")  # a rollback by version
    assert code == 0, out
    assert server.lines() == [APP.format("0.72.2"), DOCS.format("0.72.2")]
    assert server.state("held") == "0.72.2"

    server.newest("0.74.0")
    code, log, _ = server.run()  # held: the timer leaves it there
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]
    assert server.lines()[0] == APP.format("0.72.2")

    code, log, out = server.run("--release")
    assert code == 0, out
    assert server.lines()[0] == APP.format("0.74.0")
    assert server.state("held") is None


def test_check_changes_nothing(server):
    server.compose("latest", "main")
    server.newest("0.73.0")
    code, log, out = server.run("--check")
    assert code == 0
    assert log == []
    assert server.lines() == [APP.format("latest"), MAIN]
    assert "+    image: ghcr.io/facchini-miguel/kaladrius:0.73.0" in out
    assert "Would pull" in out


def test_a_deploy_running_in_dokploy_waits_for_the_next_run(server):
    (server.dir / "status").write_text("running\n")
    server.newest("0.73.0")
    code, log, _ = server.run()
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]
    assert server.lines()[0] == APP.format("0.72.2")


@pytest.mark.parametrize(
    "trouble",
    ["pull-fails", "github-down", "two app lines"],
)
def test_a_failure_before_any_change_changes_nothing_and_tells_the_monitor(server, trouble):
    server.newest("0.73.0")
    if trouble == "two app lines":
        text = (server.dir / "compose.yml").read_text()
        worker = "  worker:\n    image: ghcr.io/facchini-miguel/kaladrius:0.72.2\n"
        (server.dir / "compose.yml").write_text(text + worker)
    else:
        (server.dir / trouble).write_text("")
    before = (server.dir / "compose.yml").read_text()
    code, log, _ = server.run()
    assert code != 0
    assert (server.dir / "compose.yml").read_text() == before
    assert not any(line.startswith(("update", "deploy")) for line in log)
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"


def test_the_compose_variables_are_never_printed(server):
    """compose.one also brings the Compose's .env (the app's secrets): only the text is kept."""
    server.newest("0.73.0")
    _, _, out = server.run()
    assert "secret" not in out
    assert json.dumps("DJANGO_SECRET_KEY") not in out


def test_a_first_run_that_does_not_come_up_goes_back_to_latest(server):
    server.compose("latest", "main")
    server.broken("0.72.2")
    code, log, out = server.run()
    assert code == 1
    assert server.lines() == [APP.format("latest"), MAIN]
    assert "deploy latest (Back: 0.72.2 did not come up)" in log
    assert "Back on latest" in out, "the :latest system answers with its own version"
