"""Automatic rollback of the server update (decision 135): deploy/server/update.sh run with
a fake `docker` and the helpers of common.sh replaced, so no container, registry or network is
touched. Each image is a file holding its id; `docker pull` takes the id the registry has."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
UPDATE = ROOT_DIR / "deploy" / "server" / "update.sh"

pytestmark = pytest.mark.skipif(not shutil.which("flock"), reason="needs flock (util-linux)")

DOCKER = r"""#!/bin/bash
# Fake docker: images are files in $IMAGENS named after the reference, registry in $REMOTO.
arquivo() { echo "$IMAGENS/$(echo "$1" | tr '/:' '__')"; }
case "$1 $2" in
  "pull "*|"pull -q")
    nome=${@: -1}; [ -f "$(arquivo "$nome" | sed "s#$IMAGENS#$REMOTO#")" ] || exit 1
    cp "$(arquivo "$nome" | sed "s#$IMAGENS#$REMOTO#")" "$(arquivo "$nome")" ;;
  "image inspect")
    shift 2; formato=""
    [ "$1" = "--format" ] && { formato=$2; shift 2; }
    erro=0
    for nome in "$@"; do
      if [ -f "$(arquivo "$nome")" ]; then
        if [[ "$formato" == *RepoDigests* ]]; then echo "$nome@sha"
        elif [ -n "$formato" ]; then cat "$(arquivo "$nome")"; fi
      else erro=1; fi
    done
    exit $erro ;;
  "tag "*) cp "$(arquivo "$2")" "$(arquivo "$3")" ;;
  "image prune") ;;
  "image rm") echo "${@: -1}" >> "$IMAGENS/../removidas" ;;
  *) echo "docker falso: $*" >&2; exit 2 ;;
esac
"""

COMMON = r"""
DIR="{dir}"
APP_IMAGE="registro/app:latest"
DOCS_IMAGE="registro/docs:latest"
INSTALLED_IMAGE="$DIR/installed-image"
PREVIOUS_APP_IMAGE="registro/app:previous"
REFUSED_IMAGE="$DIR/refused-image"
export APP_IMAGE DOCS_IMAGE
log() {{ echo "$*" >> "$DIR/log"; }}
registry_login() {{ :; }}
installed_by_package() {{ [ -f "$DIR/linux-package" ]; }}
migrate_legacy_names() {{ :; }}
extract_deploy_files() {{ log "extrair $APP_IMAGE"; }}
install_schedules() {{ log agendamentos; }}
compose() {{ log "compose $* com $(cat "$IMAGENS/$(echo "$APP_IMAGE" | tr '/:' '__')")"; }}
restore_compose_from() {{ log "compose de $(cat "$IMAGENS/$(echo "$1" | tr '/:' '__')")"; }}
save_previous_compose() {{ log "guardar compose"; }}
reload_caddy() {{ log caddy; }}
notify_monitor() {{ log "monitor $1 ${{2:-ok}}"; }}
# Answers from $DIR/saude, one per line (0 = up, 1 = down); up when it runs out.
system_up() {{
  local resposta
  resposta=$(head -1 "$DIR/saude" 2>/dev/null || echo 0)
  sed -i 1d "$DIR/saude" 2>/dev/null || true
  log "saude $resposta"
  return "$resposta"
}}
"""


@pytest.fixture
def server(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for folder in ("imagens", "remoto", "path"):
        (tmp_path / folder).mkdir()
    shutil.copy(UPDATE, bin_ / "update.sh")
    (bin_ / "common.sh").write_text(textwrap.dedent(COMMON.format(dir=tmp_path)))
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER)
    docker.chmod(0o755)
    (tmp_path / ".env").write_text("SITE_HOSTNAME=exemplo.test\n")

    class Server:
        dir = tmp_path

        def image(self, place, name, ident):
            (tmp_path / place / name.replace("/", "_").replace(":", "_")).write_text(ident + "\n")

        def local_id(self, name):
            file = tmp_path / "imagens" / name.replace("/", "_").replace(":", "_")
            return file.read_text().strip() if file.exists() else None

        def health(self, *answers_list):
            (tmp_path / "saude").write_text("".join(f"{r}\n" for r in answers_list))

        def run(self, *args):
            (tmp_path / "log").write_text("")
            environment = {
                "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
                "IMAGENS": str(tmp_path / "imagens"),
                "REMOTO": str(tmp_path / "remoto"),
            }
            result = subprocess.run(  # noqa: S603 (the test's own script and arguments)
                [shutil.which("bash"), str(bin_ / "update.sh"), *args],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, (tmp_path / "log").read_text().splitlines()

        def read(self, name):
            file = tmp_path / name
            return file.read_text().split() if file.exists() else None

    s = Server()
    # Installed and running: app A and docs D; the registry has the same.
    for place in ("imagens", "remoto"):
        s.image(place, "registro/app:latest", "A")
        s.image(place, "registro/docs:latest", "D")
    s.image("imagens", "registro/app:previous", "A")
    (tmp_path / "installed-image").write_text("A\nD\n")
    return s


def test_no_new_version_changes_nothing(server):
    code, log = server.run()
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]


def test_new_version_that_starts_becomes_the_next_previous(server):
    server.image("remoto", "registro/app:latest", "B")
    server.health(0)
    code, log = server.run()
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert server.read("installed-image") == ["B", "D"]
    assert server.local_id("registro/app:previous") == "B"
    assert log[-1] == "monitor MONITOR_UPDATE_URL ok"
    # Pulled by digest (the Linux package), the image :previous named is never "dangling":
    # removed by id, the docs image still in use kept.
    assert server.read("removidas") == ["A"]


def test_new_version_that_fails_rolls_back_and_is_refused(server):
    server.image("remoto", "registro/app:latest", "B")
    server.health(1, 0)  # B does not answer; A answers again
    code, log = server.run()
    assert code == 1
    started = [row for row in log if row.startswith("compose up")]
    assert started == [
        "compose up -d --remove-orphans com B",
        "compose up -d --remove-orphans com A",
    ]
    # A's own Compose file and Caddyfile go back first: they name the Caddy and PostgreSQL
    # digests (decision 138), so a broken one of B is undone too; then Caddy reloads.
    round_trip = log.index("compose up -d --remove-orphans com A")
    assert log[round_trip - 1] == "compose de A"
    assert log[round_trip + 1] == "caddy"
    assert server.read("installed-image") == ["A", "D"]  # still the last good one
    assert server.read("refused-image") == ["B", "D"]
    assert server.local_id("registro/app:previous") == "A"
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"

    # Next runs: the refused version is not tried again, and the monitor stays red.
    code, log = server.run()
    assert code == 0
    assert not any(row.startswith("compose") for row in log)
    assert log == ["monitor MONITOR_UPDATE_URL fail"]

    # A newer version is tried, and once it comes up the refusal is gone.
    server.image("remoto", "registro/app:latest", "C")
    server.health(0)
    code, log = server.run()
    assert code == 0
    assert "compose up -d --remove-orphans com C" in log
    assert server.read("installed-image") == ["C", "D"]
    assert server.read("refused-image") is None
    assert server.read("removidas") == ["A", "B"]  # the old :previous and the refused one


def test_two_refused_versions_in_a_row_do_not_stay_on_disk(server):
    server.image("remoto", "registro/app:latest", "B")
    server.health(1, 0)
    server.run()
    # C refused too: B is not needed any more, and only the latest refusal is kept.
    server.image("remoto", "registro/app:latest", "C")
    server.health(1, 0)
    code, _log = server.run()
    assert code == 1
    assert server.read("refused-image") == ["C", "D"]
    assert server.read("removidas") == ["B"]  # never A (running again) or D (in use)
    server.image("remoto", "registro/app:latest", "E")
    server.health(0)
    code, _log = server.run()
    assert code == 0
    assert server.read("removidas") == ["B", "A", "C"]


def test_force_retries_the_refused_version(server):
    server.image("remoto", "registro/app:latest", "B")
    server.health(1, 0)
    server.run()
    server.health(0)
    code, log = server.run("--force")
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert server.read("installed-image") == ["B", "D"]


def test_old_server_keeps_previous_on_first_run(server):
    (server.dir / "imagens" / "registro_app_previous").unlink()
    code, _log = server.run()
    assert code == 0
    assert server.local_id("registro/app:previous") == "A"


def test_without_saved_previous_warns_and_does_not_pretend_rollback(server):
    (server.dir / "imagens" / "registro_app_previous").unlink()
    (server.dir / "installed-image").write_text("X\nD\n")  # A was never confirmed
    server.image("remoto", "registro/app:latest", "B")
    server.health(1)
    code, log = server.run()
    assert code == 1
    assert [row for row in log if row.startswith("compose up")] == [
        "compose up -d --remove-orphans com B"
    ]
    assert server.read("refused-image") == ["B", "D"]
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"


def test_linux_package_without_docs_and_local_only_image(server):
    # Installed from the Linux package (decision 140): no docs image, and an image already on
    # the server is enough when the registry does not have it (a test image, no internet).
    common = server.dir / "bin" / "common.sh"
    common.write_text(
        common.read_text().replace('DOCS_IMAGE="registro/docs:latest"', 'DOCS_IMAGE=""')
    )
    (server.dir / "linux-package").write_text("VERSION=0.54.0\n")
    (server.dir / "installed-image").write_text("A\n")
    server.image("imagens", "registro/app:latest", "B")
    (server.dir / "remoto" / "registro_app_latest").unlink()
    code, log = server.run()
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert server.read("installed-image") == ["B"]


def test_google_cloud_without_registry_fails_and_warns(server):
    # Only the Linux package goes on with the image already on the server: on Google Cloud the
    # update monitor reports a registry it cannot reach.
    (server.dir / "remoto" / "registro_app_latest").unlink()
    code, log = server.run()
    assert code == 1
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"


def test_package_without_image_in_registry_or_server_fails_and_warns(server):
    (server.dir / "linux-package").write_text("VERSION=0.54.0\n")
    for place in ("imagens", "remoto"):
        (server.dir / place / "registro_app_latest").unlink()
    code, log = server.run()
    assert code == 1
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"
    assert not [row for row in log if row.startswith("compose")]


def test_old_force_name_still_works(server):
    # The VM's startup script of a server created before decision 147 still says --forcar.
    server.image("remoto", "registro/app:latest", "B")
    server.health(1, 0)
    server.run()
    server.health(0)
    code, log = server.run("--forcar")
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
