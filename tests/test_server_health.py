"""The external monitor and planned stops (decision 209): deploy/server/health.sh sourced with
the real common.sh, its network helpers replaced, so nothing on the network is touched."""

import shutil
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent / "deploy" / "server"

pytestmark = pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")

# Run after sourcing health.sh: the site answers unless $DIR/down exists, and each certificate
# read takes the next line of $DIR/days (30 when they run out).
SCRIPT = r"""
source "{server}/health.sh"
DIR="{dir}"
notify_monitor() {{ echo "monitor $1 ${{2:-ok}}" >> "$DIR/log"; }}
health_answers() {{ [ ! -f "$DIR/down" ]; }}
curl() {{ [ ! -f "$DIR/down" ]; }}
sleep() {{ :; }}
certificate_days() {{
  local days
  days=$(head -1 "$DIR/days" 2>/dev/null); sed -i 1d "$DIR/days" 2>/dev/null || true
  echo "${{days:-30}}"
}}
{call}
"""


@pytest.fixture
def server(tmp_path):
    (tmp_path / ".env").write_text(
        "SITE_HOSTNAME=sistema.test\nDOCS_HOSTNAME=docs.test\n"
        "MONITOR_SYSTEM_URL=https://hc.test/s\nMONITOR_CERTIFICATE_URL=https://hc.test/c\n"
        "MONITOR_DOCS_URL=https://hc.test/d\n"
    )

    class Server:
        dir = tmp_path

        def run(self, call="check_sites"):
            (tmp_path / "log").write_text("")
            script = textwrap.dedent(SCRIPT.format(server=SERVER_DIR, dir=tmp_path, call=call))
            result = subprocess.run(  # noqa: S603 (the test's own script)
                [shutil.which("bash"), "-c", script],
                env={"PATH": "/usr/bin:/bin", "MAINTENANCE_FLAG": str(tmp_path / "maintenance")},
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, result.stderr
            return (tmp_path / "log").read_text().splitlines(), result.stdout

    return Server()


def test_sites_up_signal_success(server):
    log, _ = server.run()
    assert log == [
        "monitor MONITOR_SYSTEM_URL ok",
        "monitor MONITOR_CERTIFICATE_URL ok",
        "monitor MONITOR_DOCS_URL ok",
    ]


def test_site_down_signals_failure(server):
    (server.dir / "down").touch()
    log, _ = server.run()
    assert "monitor MONITOR_SYSTEM_URL fail" in log
    assert "monitor MONITOR_DOCS_URL fail" in log


def test_during_maintenance_nothing_is_signaled(server):
    """The demo reset or an update stops the app on purpose: no failure, and no success."""
    (server.dir / "down").touch()
    log, out = server.run("begin_maintenance; check_sites")
    assert log == []
    assert "Maintenance in progress" in out


def test_maintenance_ended_signals_again(server):
    log, _ = server.run("begin_maintenance; end_maintenance; check_sites")
    assert "monitor MONITOR_SYSTEM_URL ok" in log
    assert not (server.dir / "maintenance").exists()


@pytest.mark.parametrize("content", ["old", "garbage"])
def test_forgotten_or_broken_flag_does_not_silence_the_monitor(server, content):
    """A script that died without ending its maintenance silences health.sh for 30 minutes at
    most; an unreadable flag never."""
    began = int(time.time()) - 31 * 60 if content == "old" else "x"
    (server.dir / "maintenance").write_text(f"{began}\n")
    (server.dir / "down").touch()
    log, _ = server.run()
    assert "monitor MONITOR_SYSTEM_URL fail" in log


def test_certificate_read_once_more_before_failing(server):
    """One connection lost while the proxy reloads reads as 0 days: a second read decides."""
    (server.dir / "days").write_text("0\n")
    log, _ = server.run()
    assert "monitor MONITOR_CERTIFICATE_URL ok" in log


def test_certificate_expiring_fails(server):
    (server.dir / "days").write_text("10\n10\n")
    log, _ = server.run()
    assert "monitor MONITOR_CERTIFICATE_URL fail" in log


def test_write_metrics_replaces_the_file_whole(server):
    """Decision 211: node-exporter reads $DIR/metrics/*.prom; a file is replaced at once."""
    call = (
        'METRICS_DIR="$DIR/metrics"; printf "a 1\\n" | write_metrics backup; '
        'printf "a 2\\nb 3\\n" | write_metrics backup'
    )
    server.run(call)
    folder = server.dir / "metrics"
    assert (folder / "backup.prom").read_text() == "a 2\nb 3\n"
    assert [p.name for p in folder.iterdir()] == ["backup.prom"]  # no temporary file left
    assert oct((folder / "backup.prom").stat().st_mode)[-3:] == "644"


def test_write_metrics_never_fails_the_script(server):
    (server.dir / "metrics").write_text("not a folder")
    call = 'METRICS_DIR="$DIR/metrics/x"; echo "a 1" | write_metrics backup; echo after'
    _, out = server.run(call)
    assert out.strip().endswith("after")
