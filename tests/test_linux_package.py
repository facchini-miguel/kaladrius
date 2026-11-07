"""The Linux package (.deb, .rpm and Arch Linux, decision 140): what deploy/package/nfpm.yaml
ships, the package mode of deploy/server/common.sh, and the `kaladrius` command. The installation
itself (apt and dnf, the text screens, backups, the restore test, an update and its rollback) is
tested for real in a clean virtual machine before each change; see deploy/package/README.md."""

import base64
import hashlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGE = ROOT_DIR / "deploy" / "package"
SERVER = ROOT_DIR / "deploy" / "server"
NFPM = (PACKAGE / "nfpm.yaml").read_text()

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")


def content():
    """The (src, dst) pairs of the package's contents."""
    return re.findall(r"- src: (\S+)\n\s+dst: (\S+)", NFPM)


def test_every_package_file_exists():
    for source, _destination in content():
        if (
            source.startswith("/") or source == "dist/linux-package"
        ):  # a symlink; written by build.sh
            continue
        assert (ROOT_DIR / source).is_file(), source
    for script in re.findall(r"(?:postinstall|postupgrade|preremove|postremove): (\S+)", NFPM):
        assert (ROOT_DIR / script).is_file(), script


def test_each_scheduled_task_runs_a_package_script():
    destinations = {destination for _source, destination in content()}
    units = [d for d in destinations if d.startswith("/usr/lib/systemd/system/")]
    assert {Path(u).name for u in units} == {
        f"kaladrius-{name}.{kind}"
        for name in ("backup", "health", "restore-test")
        for kind in ("service", "timer")
    }
    for unit in units:
        if unit.endswith(".service"):
            text = (SERVER / Path(unit).name).read_text()
            executable = re.search(r"^ExecStart=(\S+)", text, re.M).group(1)
            assert executable in destinations, (unit, executable)


def test_package_enables_the_tasks_it_ships():
    shared = (SERVER / "common.sh").read_text()
    block = shared.split("if installed_by_package; then  # its units came with the package")[1]
    turned_on_ones = set(re.findall(r"kaladrius-[a-z-]+\.timer", block.split("return 0")[0]))
    brought = {Path(d).name for _o, d in content() if d.endswith(".timer")}
    assert turned_on_ones == brought
    # Also when the package is installed again over a configured installation, before the
    # system is started: a removal disabled them, and the new version may not come up.
    install = (PACKAGE / "post_install.sh").read_text().split('if [ -f "$DIR/.env" ]')[1]
    before_start = install.split('"$DIR/bin/update.sh"')[0]
    assert set(re.findall(r"kaladrius-[a-z-]+\.timer", before_start)) == brought


def shared_in(folder, package=None, env=""):
    """common.sh with its DIR in a temporary folder."""
    (folder / "release").mkdir(parents=True, exist_ok=True)
    text = (SERVER / "common.sh").read_text().replace("DIR=/opt/kaladrius", f"DIR={folder}", 1)
    (folder / "common.sh").write_text(text)
    if package is not None:
        (folder / "release" / "linux-package").write_text(package)
    (folder / ".env").write_text(env)
    return folder / "common.sh"


def evaluate(shared, expression, environment=None):
    result = subprocess.run(  # noqa: S603 (the test's own script)
        [BASH, "-c", f'source "{shared}"; {expression}'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(environment or {})},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


IMAGE = "ghcr.io/facchini-miguel/kaladrius:0.54.0@sha256:abc"


def test_package_mode_uses_image_pinned_by_digest(tmp_path):
    shared = shared_in(tmp_path, package=f"VERSION=0.54.0\nIMAGE={IMAGE}\n")
    assert evaluate(shared, 'echo "$APP_IMAGE|$DOCS_IMAGE|$PACKAGE_VERSION|$REGISTRY"') == (
        f"{IMAGE}||0.54.0|ghcr.io"
    )
    assert evaluate(shared, 'echo "$PREVIOUS_APP_IMAGE"') == (
        "ghcr.io/facchini-miguel/kaladrius:previous"
    )
    # No registry login: the image is public.
    assert evaluate(shared, "registry_login && echo sem-login") == "sem-login"


def test_package_mode_accepts_another_image(tmp_path):
    shared = shared_in(
        tmp_path, package=f"VERSION=0.54.0\nIMAGE={IMAGE}\n", env="KALADRIUS_IMAGE=k:teste\n"
    )
    assert evaluate(shared, 'echo "$APP_IMAGE $PREVIOUS_APP_IMAGE"') == "k:teste k:previous"
    assert evaluate(shared, 'echo "$APP_IMAGE"', {"KALADRIUS_IMAGE": "outra:1"}) == "outra:1"


def test_without_package_follows_google_cloud(tmp_path):
    shared = shared_in(tmp_path)
    # Google Cloud copies the whole deploy/ folder of the image to release/, the package's
    # sources included: they must not switch on the package mode.
    shutil.copytree(PACKAGE, tmp_path / "release" / "package")
    app, docs, previous = evaluate(
        shared, 'echo "$APP_IMAGE $DOCS_IMAGE $PREVIOUS_APP_IMAGE"'
    ).split()
    assert app.endswith("/kaladrius/app:latest") and docs.endswith("/kaladrius/docs:latest")
    assert previous.endswith("/kaladrius/app:previous")


@pytest.mark.parametrize(
    ("reference", "repository"),
    [
        ("ghcr.io/a/b:1.0@sha256:abc", "ghcr.io/a/b"),
        ("us-east1-docker.pkg.dev/p/k/app:latest", "us-east1-docker.pkg.dev/p/k/app"),
        ("localhost:5000/x", "localhost:5000/x"),
        ("localhost:5000/x:2", "localhost:5000/x"),
        ("kaladrius:teste", "kaladrius"),
    ],
)
def test_repository_of(tmp_path, reference, repository):
    assert evaluate(shared_in(tmp_path), f'repository_of "{reference}"') == repository


@pytest.mark.parametrize(
    ("access", "expected"),
    [("internal-network", "sim"), ("rede-interna", "sim"), ("internet", "nao")],
)
def test_internal_network(tmp_path, access, expected):
    shared = shared_in(tmp_path, env=f"KALADRIUS_ACCESS={access}\n")
    assert evaluate(shared, "internal_network && echo sim || echo nao") == expected


def kaladrius(tmp_path, *args, language="C"):
    """The `kaladrius` command as installed: beside common.sh, here with DIR in tmp_path."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACKAGE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(shared_in(tmp_path), bin_ / "common.sh")
    return subprocess.run(  # noqa: S603 (the package's own command)
        [BASH, str(bin_ / "kaladrius"), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": language},
        timeout=30,
    )


@pytest.mark.parametrize(
    ("language", "excerpt"),
    [
        ("pt_BR.UTF-8", "faz um backup agora"),
        ("es_ES.UTF-8", "hace una copia de seguridad ahora"),
        ("en_US.UTF-8", "makes a backup now"),
        ("C", "makes a backup now"),
    ],
)
def test_help_in_the_server_language(tmp_path, language, excerpt):
    result = kaladrius(tmp_path, "help", language=language)
    assert result.returncode == 0, result.stderr
    assert excerpt in result.stdout
    assert "sudo kaladrius configure" in result.stdout


@pytest.mark.parametrize("command", ["ajuda", "ayuda", "--help"])
def test_help_under_other_names(tmp_path, command):
    assert kaladrius(tmp_path, command).returncode == 0


def test_unknown_command_fails(tmp_path):
    assert kaladrius(tmp_path, "nao-existe").returncode == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="running as root")
def test_configure_requires_root(tmp_path):
    result = kaladrius(tmp_path, "configure", "--access", "internal-network")
    assert result.returncode == 1
    assert "sudo kaladrius configure" in result.stderr


def test_no_script_checks_two_conditions_on_one_line():
    # `[ a ] && [ b ]` alone on a line does not stop a `set -e` script when `a` fails: the
    # restore test passed with no clinic restored until decision 140.
    default = re.compile(r"^\s*\[[^]]*\]\s*&&\s*\[[^]]*\]\s*$")
    for script in [*SERVER.glob("*.sh"), *PACKAGE.glob("*.sh"), PACKAGE / "kaladrius"]:
        for number, row in enumerate(script.read_text().splitlines(), 1):
            assert not default.match(row), f"{script.name}:{number}: {row.strip()}"


def test_no_script_uses_grep_q_after_a_pipe():
    # With pipefail, `cmd | grep -q x` fails when grep exits at the first match and `cmd` dies
    # writing the rest (SIGPIPE): Kaladrius's own Caddy was taken for another program on 80/443.
    default = re.compile(r"\|\s*grep\s+-[a-zA-Z]*q")
    for script in [*SERVER.glob("*.sh"), *PACKAGE.glob("*.sh"), PACKAGE / "kaladrius"]:
        for number, row in enumerate(script.read_text().splitlines(), 1):
            assert not default.search(row), f"{script.name}:{number}: {row.strip()}"


@pytest.mark.parametrize(
    ("address", "is_valid"),
    [
        ("192.168.0.10", True),
        ("10.0.0.255", True),
        ("192.168.0.08", True),  # a leading zero is not octal
        ("192.168.0.300", False),
        ("300.1.1.999", False),
        ("192.168.0", False),
        ("clinica.exemplo.com", False),
    ],
)
def test_is_ipv4(tmp_path, address, is_valid):
    result = command_function(
        tmp_path, f'is_ipv4 "{address}" && echo sim || echo nao', {"PATH": "/usr/bin:/bin"}
    )
    assert result.stdout.strip() == ("sim" if is_valid else "nao"), result.stderr


def test_configuring_again_saves_the_new_admin_user(tmp_path):
    # A first run that did not finish wrote .env; the user name typed on the next run is the
    # one created, so .env (read by `kaladrius senha`) must say the same.
    expression = (
        'rm "$DIR/.env"; write_env internal-network 192.168.0.10 admin a@x.test; '
        'write_env internal-network 192.168.0.11 suporte ""; '
        'grep -c DJANGO_SECRET_KEY "$DIR/.env"; env_value DJANGO_ADMIN_USERNAME; '
        "env_value DJANGO_ADMIN_EMAIL; env_value SITE_HOSTNAME"
    )
    result = command_function(tmp_path, expression, {"PATH": "/usr/bin:/bin"})
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["1", "suporte", "", "192.168.0.11"]


def test_backups_folder(tmp_path):
    assert evaluate(shared_in(tmp_path / "a"), "backup_dir") == "/var/backups/kaladrius"
    other_one = shared_in(tmp_path / "b", env="KALADRIUS_BACKUP_DIR=/srv/copias\n")
    assert evaluate(other_one, "backup_dir") == "/srv/copias"
    # A .env of 0.54 or earlier, not migrated yet (decision 147).
    old_one = shared_in(tmp_path / "c", env="KALADRIUS_BACKUP_PASTA=/srv/antigas\n")
    assert evaluate(old_one, "backup_dir") == "/srv/antigas"


def test_caddy_never_gets_an_empty_docs_address():
    # An empty address makes the Caddyfile's docs block invalid and Caddy does not start.
    compose = (ROOT_DIR / "deploy" / "docker-compose.prod.yml").read_text()
    assert "DOCS_HOSTNAME: ${DOCS_HOSTNAME:-docs.localhost}" in compose


def test_removing_the_package_never_deletes_data():
    # The database, the backups and the .env stay; the help printed after a removal shows the
    # commands, for a person to decide (indented lines of the message).
    for script in ("pre_remove.sh", "post_remove.sh"):
        for row in (PACKAGE / script).read_text().splitlines():
            if row.lstrip().startswith(("#", "printf")) or row.startswith("    sudo "):
                continue
            assert "volume rm" not in row and "down -v" not in row, row
            if re.search(r"\brm\b", row):
                # The package repository's apt source (on a purge) is configuration, not data.
                assert row.strip() in {
                    "rm -f /opt/kaladrius/release/.env",
                    'rm -f "$ETC/apt/sources.list.d/kaladrius.sources"',
                }, row


def test_site_is_checked_by_the_server_itself(tmp_path):
    # A clinic's router often has no "hairpin NAT": from inside, the clinic's public address
    # never answers, and a good new version would be refused.
    package = f"VERSION=0.54.0\nIMAGE={IMAGE}\n"
    expression = 'site_curl_options k.example; echo "${CURL_OPTIONS[*]}"'
    internet = shared_in(tmp_path / "a", package=package, env="KALADRIUS_ACCESS=internet\n")
    assert evaluate(internet, expression) == "--resolve k.example:443:127.0.0.1"
    internal = shared_in(tmp_path / "b", package=package, env="KALADRIUS_ACCESS=internal-network\n")
    assert evaluate(internal, expression) == "--insecure"
    # Google Cloud: through the internet, like anyone.
    assert evaluate(shared_in(tmp_path / "c"), expression) == ""


FAKE_DOCKER = """#!/bin/bash
# docker image inspect [--format F] IMAGE: the id in $IMAGENS/<image>, or a failure.
[ "$1 $2" = "image inspect" ] || exit 2
nome=${@: -1}
arquivo="$IMAGENS/$(echo "$nome" | tr '/:@' '___')"
[ -f "$arquivo" ] || exit 1
[ "$3" = "--format" ] && cat "$arquivo"
exit 0
"""


def shared_with_images(tmp_path, images, refused=None):
    """common.sh in package mode, with a fake `docker` that knows only `imagens` (name: id)."""
    shared = shared_in(tmp_path, package="VERSION=0.55.0\nIMAGE=kaladrius:nova\n")
    (tmp_path / "imagens").mkdir()
    for name, ident in images.items():
        (tmp_path / "imagens" / name.replace(":", "_")).write_text(ident)
    (tmp_path / "path").mkdir()
    docker = tmp_path / "path" / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    if refused is not None:
        (tmp_path / "refused-image").write_text(refused + "\n")
    environment = {
        "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
        "IMAGENS": str(tmp_path / "imagens"),
    }
    return shared, environment


# Decided by common.sh itself, for every script that sources it.
LIVE_VERSION = 'echo "$APP_IMAGE $COMPOSE_PATH"'


def test_after_rollback_commands_stay_on_previous_version(tmp_path):
    shared, environment = shared_with_images(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, refused="B"
    )
    (tmp_path / "previous").mkdir()
    (tmp_path / "previous" / "docker-compose.prod.yml").write_text("")
    assert evaluate(shared, LIVE_VERSION, environment) == (
        f"kaladrius:previous {tmp_path}/previous/docker-compose.prod.yml"
    )


def test_update_picks_the_version_alone(tmp_path):
    # update.sh compares the package's image with the refused one: it must see the package's.
    shared, environment = shared_with_images(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, refused="B"
    )
    assert evaluate(shared, 'echo "$ON_PREVIOUS"', environment) == "1"
    updating = {**environment, "UPDATING": "1"}
    assert evaluate(shared, f'{LIVE_VERSION}; echo "[$ON_PREVIOUS]"', updating) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml\n[]"
    )


def test_previous_without_compose_copy_uses_the_package_one(tmp_path):
    shared, environment = shared_with_images(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, refused="B"
    )
    assert evaluate(shared, LIVE_VERSION, environment) == (
        f"kaladrius:previous {tmp_path}/release/docker-compose.prod.yml"
    )


@pytest.mark.parametrize(
    ("images", "refused"),
    [
        ({"kaladrius:nova": "B", "kaladrius:previous": "A"}, None),  # nothing refused
        ({"kaladrius:nova": "C", "kaladrius:previous": "A"}, "B"),  # a newer package since
        ({"kaladrius:nova": "B"}, "B"),  # a first installation that did not come up
    ],
)
def test_without_rollback_commands_use_package_version(tmp_path, images, refused):
    shared, environment = shared_with_images(tmp_path, images, refused)
    assert evaluate(shared, LIVE_VERSION, environment) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml"
    )


def test_started_version_keeps_compose_and_caddyfile(tmp_path):
    shared = shared_in(tmp_path, package=f"VERSION=0.54.0\nIMAGE={IMAGE}\n")
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.54.0")
    (tmp_path / "release" / "Caddyfile").write_text("caddy 0.54.0")
    evaluate(shared, "save_previous_compose")
    # The package replaces release/ with the next version's; the copy stays.
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.55.0")
    assert (tmp_path / "previous" / "docker-compose.prod.yml").read_text() == "compose 0.54.0"
    assert (tmp_path / "previous" / "Caddyfile").read_text() == "caddy 0.54.0"
    assert os.readlink(tmp_path / "previous" / ".env") == "../.env"
    assert evaluate(shared, 'restore_compose_from x && echo "$COMPOSE_PATH"') == (
        f"{tmp_path}/previous/docker-compose.prod.yml"
    )


def command_function(tmp_path, expression, environment):
    """Runs `expressao` with the functions of the `kaladrius` command defined."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACKAGE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(shared_in(tmp_path), bin_ / "common.sh")
    return subprocess.run(  # noqa: S603 (the package's own command)
        # $0 is the command's path, as when it runs: it finds common.sh beside itself.
        [BASH, "-c", f'source "$0" version >/dev/null; {expression}', str(bin_ / "kaladrius")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )


UNROUTABLE_IP = """#!/bin/sh
# A clinic's network with no way out: no default route.
case "$*" in
  "-4 route get 1.1.1.1") echo "RTNETLINK answers: Network is unreachable" >&2; exit 2 ;;
  "-4 -o addr show scope global")
    echo "2: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0"
    echo "3: enp1s0    inet 192.168.0.10/24 brd 192.168.0.255 scope global enp1s0" ;;
esac
"""


def test_local_address_on_a_network_without_route(tmp_path):
    (tmp_path / "path").mkdir()
    ip = tmp_path / "path" / "ip"
    ip.write_text(UNROUTABLE_IP)
    ip.chmod(0o755)
    result = command_function(
        tmp_path, "local_address", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "192.168.0.10"


def test_local_address_without_any_address_does_not_fail(tmp_path):
    (tmp_path / "path").mkdir()
    ip = tmp_path / "path" / "ip"
    ip.write_text("#!/bin/sh\nexit 2\n")
    ip.chmod(0o755)
    result = command_function(
        tmp_path, "local_address; echo fim", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "fim\n"


CALL_LOG = """#!/bin/sh
echo "$(basename "$0") $*" >> "$CHAMADAS"
"""


def fakes(folder, *commands):
    """Fake `comandos` in `pasta` that only record their calls; returns the calls file and an
    environment with them first in PATH."""
    folder.mkdir(exist_ok=True)
    for command in commands:
        fake = folder / command
        fake.write_text(CALL_LOG)
        fake.chmod(0o755)
    calls = folder / "chamadas"
    calls.write_text("")
    return calls, {"PATH": f"{folder}:/usr/bin:/bin", "CHAMADAS": str(calls)}


@pytest.mark.parametrize(
    ("argument", "remove"),
    [
        ("remove", True),  # apt
        ("0", True),  # rpm: the last copy goes
        ("0.54.0-1", True),  # pacman runs pre_remove (with the version) only on a removal
        ("upgrade", False),  # apt: an update
        ("1", False),  # rpm: an update (one copy stays)
        ("failed-upgrade", False),
    ],
)
def test_remove_stops_the_system_only_on_removal(tmp_path, argument, remove):
    calls, environment = fakes(tmp_path / "path", "systemctl", "docker")
    result = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(PACKAGE / "pre_remove.sh"), argument],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    turned_off_flag = "disable --now kaladrius-backup.timer" in calls.read_text()
    assert turned_off_flag is remove, calls.read_text()


def test_each_format_has_the_docker_dependencies():
    # Each package format names Docker and Docker Compose in its own distributions' words.
    for format_ in ("deb", "rpm", "archlinux"):
        block = re.search(rf"^  {format_}:\n((?:    .*\n)+)", NFPM, re.M).group(1)
        dependencies = block.split("depends:")[1].split("recommends:")[0]
        assert "docker" in dependencies and "compose" in dependencies, format_


def test_text_mode_password_keeps_spaces(tmp_path):
    # Without whiptail (openSUSE, Arch Linux) the password is read as typed, spaces included.
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    shutil.copy(PACKAGE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(shared_in(tmp_path), bin_ / "common.sh")
    result = subprocess.run(  # noqa: S603 (the package's own command)
        [
            BASH,
            "-c",
            'source "$0" version >/dev/null; ask_password "Senha:"',
            str(bin_ / "kaladrius"),
        ],
        input="  minha senha \n",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "KALADRIUS_NO_SCREENS": "1"},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "  minha senha "


@pytest.mark.parametrize("language", ["pt_BR.UTF-8", "es_ES.UTF-8", "C"])
def test_help_explains_both_ways_to_update(tmp_path, language):
    # With the package repository (which the package adds), the system's updates; on Arch
    # Linux or without it, the next version's package from the releases.
    output = kaladrius(tmp_path, "help", language=language).stdout
    for command in ("sudo apt upgrade", "sudo dnf upgrade", "sudo zypper update", "pacman -U"):
        assert command in output
    assert "github.com/facchini-miguel/kaladrius/releases" in output


def test_certificate_with_caddy_stopped_leaves_no_file(tmp_path):
    destination = tmp_path / "kaladrius-certificate.crt"
    expression = (
        "require_root() { :; }; compose() { return 1; }; "
        f'echo KALADRIUS_ACCESS=internal-network > "$DIR/.env"; certificate "{destination}"'
    )
    result = command_function(tmp_path, expression, {"PATH": "/usr/bin:/bin"})
    assert result.returncode == 1
    assert "sudo kaladrius start" in result.stderr
    assert not destination.exists()


def after_install(tmp_path, argument, created_admin, environment=None, configured=True):
    """post_install.sh with DIR and ETC in tmp_path, beside the real common.sh (its DIR there
    too); systemctl, systemd-run, docker and update.sh faked, the systemd units' folder in
    tmp_path."""
    dir_ = tmp_path / "opt"
    (dir_ / "release").mkdir(parents=True, exist_ok=True)
    (dir_ / "bin").mkdir(exist_ok=True)
    shutil.copytree(PACKAGE / "repository", dir_ / "repository", dirs_exist_ok=True)
    (dir_ / "release" / "linux-package").write_text(f"VERSION=0.55.0\nIMAGE={IMAGE}\n")
    text = (SERVER / "common.sh").read_text().replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
    (dir_ / "bin" / "common.sh").write_text(text)
    if configured and not (dir_ / ".env").exists():
        (dir_ / ".env").write_text("SITE_HOSTNAME=192.168.0.10\n")
    if created_admin:
        (dir_ / "admin-created").write_text("")
    calls, fake_environment = fakes(tmp_path / "path", "systemctl", "systemd-run", "docker")
    update = dir_ / "bin" / "update.sh"
    update.write_text(CALL_LOG)
    update.chmod(0o755)
    script = tmp_path / "post_install.sh"
    text = (PACKAGE / "post_install.sh").read_text()
    text = text.replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
    script.write_text(text.replace("ETC=/etc", f"ETC={tmp_path / 'etc'}", 1))
    (tmp_path / "systemd").mkdir(exist_ok=True)
    result = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(script), argument],
        capture_output=True,
        text=True,
        env={**fake_environment, "SYSTEMD_DIR": str(tmp_path / "systemd"), **(environment or {})},
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout, calls.read_text()


def test_reinstall_without_admin_asks_again(tmp_path):
    # A first `configure` that stopped after writing .env: installing the package again must not
    # bring the system up with no account to log in.
    output, calls = after_install(tmp_path, "1", created_admin=False)
    assert "update.sh" not in calls
    assert "sudo kaladrius configure" in output


def test_updating_configured_package_starts_new_version(tmp_path):
    _output, calls = after_install(tmp_path, "2", created_admin=True)
    assert "update.sh --force" in calls
    assert "systemd-run" not in calls


def test_pacman_update_carries_the_variables(tmp_path):
    # pacman: update.sh runs as its own systemd unit, which starts with a clean environment. The
    # names of 0.54 and earlier (decision 147) still work, and go along under the new ones.
    for environment in (
        {"KALADRIUS_IMAGE": "kaladrius:teste", "HEALTH_WAIT": "60"},
        {"KALADRIUS_IMAGEM": "kaladrius:teste", "SAUDE_ESPERA": "60"},
    ):
        _output, calls = after_install(
            tmp_path, "0.55.0-1", created_admin=True, environment=environment
        )
        row = next(c for c in calls.splitlines() if c.startswith("systemd-run"))
        assert "--setenv=KALADRIUS_IMAGE=kaladrius:teste" in row
        assert "--setenv=HEALTH_WAIT=60" in row
        assert "--unit=kaladrius-package-update" in row


@pytest.mark.parametrize(
    ("admin_created_hours_ago", "failure"),
    [
        (None, False),  # the setup has not finished
        (3, False),  # installed hours ago, before the first daily backup
        (24 * 30, True),  # a month later no backup at all is a failure: a disk not mounted?
    ],
)
def test_restore_test_without_backup(tmp_path, admin_created_hours_ago, failure):
    shared_in(
        tmp_path,
        package=f"VERSION=0.54.0\nIMAGE={IMAGE}\n",
        env=(
            f"KALADRIUS_BACKUP_DIR={tmp_path / 'nao-existe'}\n"
            "MONITOR_RESTORE_URL=http://monitor.test\n"
        ),
    )
    if admin_created_hours_ago is not None:
        admin = tmp_path / "admin-created"
        admin.write_text("")
        when = time.time() - admin_created_hours_ago * 3600
        os.utime(admin, (when, when))
    shutil.copy(SERVER / "test_restore.sh", tmp_path / "test_restore.sh")
    calls, environment = fakes(tmp_path / "path", "docker", "curl")
    result = subprocess.run(  # noqa: S603 (the server's own script)
        [BASH, str(tmp_path / "test_restore.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if failure:
        assert result.returncode != 0
        assert "No backup in" in result.stderr
        assert "curl -fsS -m 10 --retry 3 -o /dev/null http://monitor.test/fail" in (
            calls.read_text()
        )
    else:
        assert result.returncode == 0, result.stderr
        assert "No backup in" in result.stdout and "to test yet" in result.stdout
        assert "sudo kaladrius backup" in result.stdout
        assert "curl" not in calls.read_text()  # the monitor hears no success, no failure


@pytest.mark.parametrize("command", ["start", "restart"])
def test_start_without_admin_asks_to_finish_setup(tmp_path, command):
    # A setup that stopped before the administrator: starting the system would leave nobody
    # able to log in. `logs` and `stop` still work, to see why.
    expression = (
        'require_root() { :; }; compose() { echo "compose $*"; }; echo X=1 > "$DIR/.env"; '
        f"require_admin && echo {command}"
    )
    result = command_function(tmp_path, expression, {"PATH": "/usr/bin:/bin"})
    assert result.returncode == 1
    assert "sudo kaladrius configure" in result.stderr
    (tmp_path / "admin-created").write_text("")
    result = command_function(tmp_path, expression, {"PATH": "/usr/bin:/bin"})
    assert result.stdout.strip() == command, result.stderr
    kaladrius_ = (PACKAGE / "kaladrius").read_text()
    assert re.search(
        rf"^  {command} \| \w+\) require_root {command}; require_admin;", kaladrius_, re.M
    )


FINGERPRINT = "9D3A0438FF6C00F91CA1A0ABA5C335B2EB367ABA"  # decision 142


def fingerprint(scaffold):
    """The fingerprint of an ASCII-armored OpenPGP v4 public key: SHA-1 of its first packet."""
    rows = scaffold.strip().splitlines()
    body = rows[rows.index("") + 1 : -1]
    data = base64.b64decode("".join(row for row in body if not row.startswith("=")))
    if data[0] & 0x40:  # new packet format
        size, start = (data[1], 2) if data[1] < 192 else (((data[1] - 192) << 8) + data[2] + 192, 3)
    else:  # old format: the length type in the low two bits
        n = {0: 1, 1: 2, 2: 4}[data[0] & 3]
        size, start = int.from_bytes(data[1 : 1 + n]), 1 + n
    package = data[start : start + size]
    return hashlib.sha1(b"\x99" + len(package).to_bytes(2) + package).hexdigest().upper()  # noqa: S324


def test_shipped_repository_is_the_published_one():
    # The apt source carries the key in Signed-By (deb822: one space before each line, "." for
    # an empty one); both files point to the software's own folder on packages.facchini.eti.br.
    source_file = (PACKAGE / "repository" / "kaladrius.sources").read_text()
    assert "URIs: https://packages.facchini.eti.br/kaladrius/deb\n" in source_file
    assert "Suites: stable\nComponents: main\nArchitectures: amd64\n" in source_file
    rows = source_file.split("Signed-By:\n", 1)[1].splitlines()
    key = "\n".join("" if row == " ." else row.removeprefix(" ") for row in rows)
    assert fingerprint(key) == FINGERPRINT
    repo = (PACKAGE / "repository" / "kaladrius.repo").read_text()
    for row in (
        "baseurl=https://packages.facchini.eti.br/kaladrius/rpm",
        "gpgcheck=1",
        "repo_gpgcheck=1",
        "autorefresh=1",
        "gpgkey=https://packages.facchini.eti.br/facchini.asc",
    ):
        assert row in repo.splitlines()


@pytest.mark.parametrize(
    ("argument", "folders", "expected"),
    [
        ("configure", ["apt/sources.list.d"], "apt/sources.list.d/kaladrius.sources"),
        ("1", ["yum.repos.d"], "yum.repos.d/kaladrius.repo"),  # dnf
        ("2", ["yum.repos.d"], "yum.repos.d/kaladrius.repo"),  # an update from a downloaded rpm
        ("1", ["zypp/repos.d"], "zypp/repos.d/kaladrius.repo"),  # zypper
        ("0.55.0-1", ["apt/sources.list.d", "yum.repos.d"], None),  # Arch Linux: none
    ],
)
def test_package_adds_the_repository(tmp_path, argument, folders, expected):
    for folder in folders:
        (tmp_path / "etc" / folder).mkdir(parents=True)
    output, _calls = after_install(tmp_path, argument, created_admin=True)
    added = sorted(
        str(a.relative_to(tmp_path / "etc")) for a in (tmp_path / "etc").rglob("kaladrius.*")
    )
    assert added == ([expected] if expected else [])
    if expected:
        source = PACKAGE / "repository" / Path(expected).name
        assert (tmp_path / "etc" / expected).read_text() == source.read_text()
        assert "package repository added" in output


def test_configured_repository_is_not_added_again(tmp_path):
    # By hand under another name, or the file of an earlier installation, as the person left it.
    sources = tmp_path / "etc" / "apt" / "sources.list.d"
    sources.mkdir(parents=True)
    (sources / "facchini.list").write_text(
        "deb [signed-by=/etc/apt/keyrings/facchini.asc]"
        " https://packages.facchini.eti.br/kaladrius/deb stable main\n"
    )
    after_install(tmp_path, "configure", created_admin=True)
    assert sorted(a.name for a in sources.iterdir()) == ["facchini.list"]
    (sources / "facchini.list").unlink()
    # Its own file, changed by hand (another address, say): left as it is.
    (sources / "kaladrius.sources").write_text("Enabled: no\nURIs: http://espelho.exemplo/k\n")
    output, _calls = after_install(tmp_path, "configure", created_admin=True)
    assert (sources / "kaladrius.sources").read_text().startswith("Enabled: no")
    assert "package repository added" not in output


def test_no_repository_by_choice_also_on_later_installs(tmp_path):
    sources = tmp_path / "etc" / "apt" / "sources.list.d"
    sources.mkdir(parents=True)
    after_install(
        tmp_path, "configure", created_admin=True, environment={"KALADRIUS_NO_REPOSITORY": "1"}
    )
    assert not list(sources.iterdir())
    after_install(tmp_path, "configure", created_admin=True)  # a later update: still none
    assert not list(sources.iterdir())


def test_first_install_already_adds_the_repository(tmp_path):
    # Before `configure`: the server is on the repository even if the setup never finishes.
    sources = tmp_path / "etc" / "apt" / "sources.list.d"
    sources.mkdir(parents=True)
    output, _calls = after_install(tmp_path, "configure", created_admin=False, configured=False)
    assert (sources / "kaladrius.sources").exists()
    assert "sudo kaladrius configure" in output


@pytest.mark.parametrize(("argument", "fica"), [("remove", True), ("purge", False)])
def test_remove_keeps_repository_and_purge_deletes(tmp_path, argument, fica):
    sources = tmp_path / "etc" / "apt" / "sources.list.d"
    sources.mkdir(parents=True)
    (sources / "kaladrius.sources").write_text("Types: deb\n")
    script = tmp_path / "post_remove.sh"
    text = (
        (PACKAGE / "post_remove.sh").read_text().replace("ETC=/etc", f"ETC={tmp_path / 'etc'}", 1)
    )
    script.write_text(text.replace("rm -f /opt/kaladrius/", f"rm -f {tmp_path}/", 1))
    _calls, environment = fakes(tmp_path / "path", "systemctl")
    result = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(script), argument],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert ("sudo rm " + str(sources / "kaladrius.sources") in result.stdout) is fica


DOCKER_COMMANDS = """#!/bin/bash
# docker compose … exec -T app python manage.py ARGS: `help NAME` answers whether the app knows
# NAME (in $KNOWN); anything else is recorded.
args=("$@")
for i in "${!args[@]}"; do [ "${args[$i]}" = manage.py ] && break; done
rest=("${args[@]:$((i + 1))}")
if [ "${rest[0]}" = help ]; then
  case " $KNOWN " in *" ${rest[1]} "*) exit 0 ;; *) exit 1 ;; esac
fi
echo "${rest[*]}" >>"$CALLS"
"""


@pytest.mark.parametrize(
    ("known", "expected"),
    [
        ("record_backup", "record_backup a.dump 10"),
        # The previous version, after a rollback: only the name before decision 148.
        ("registrar_backup", "registrar_backup a.dump 10"),
    ],
)
def test_manage_uses_old_name_only_in_app_that_lacks_it(tmp_path, known, expected):
    shared = shared_in(tmp_path)
    (tmp_path / "path").mkdir()
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER_COMMANDS)
    docker.chmod(0o755)
    calls = tmp_path / "chamadas"
    environment = {
        "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
        "KNOWN": known,
        "CALLS": str(calls),
    }
    evaluate(shared, "manage record_backup a.dump 10 -- registrar_backup a.dump 10", environment)
    evaluate(shared, "manage health", environment)  # no old name given: always the new one
    assert calls.read_text().splitlines() == [expected, "health"]


CURL_ONLY_NEW = """#!/bin/sh
case "$*" in *"/api/v1/health"*) exit 0 ;; *) exit 22 ;; esac
"""
CURL_ONLY_OLD = """#!/bin/sh
# Only the health page's address before decision 155 answers: no longer read (decision 196).
case "$*" in *"/api/v1/saude"*) exit 0 ;; *) exit 22 ;; esac
"""


@pytest.mark.parametrize(
    ("curl", "answers"),
    [(CURL_ONLY_NEW, "sim"), (CURL_ONLY_OLD, "nao"), ("#!/bin/sh\nexit 22\n", "nao")],
)
def test_health_by_its_address(tmp_path, curl, answers):
    shared = shared_in(tmp_path)
    (tmp_path / "path").mkdir()
    fake = tmp_path / "path" / "curl"
    fake.write_text(curl)
    fake.chmod(0o755)
    environment = {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    expression = "CURL_OPTIONS=(); health_answers k.example && echo sim || echo nao"
    assert evaluate(shared, expression, environment) == answers
