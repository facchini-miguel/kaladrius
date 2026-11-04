"""The move to the names of decision 147 on a server installed with 0.54 or earlier.

On Google Cloud the first update is run by the server's own scripts of 0.54.1 (frozen copies in
tests/legacy_server/): their atualizar.sh extracts deploy/ from the new image and loads the
bridge deploy/servidor/comum.sh, which loads deploy/server/common.sh and migrates the server.
Here the "new image" is this repository's deploy/ folder, served by a fake `docker`; systemctl,
curl and the registry are faked too, and every path is inside tmp_path."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LEGADO = RAIZ / "tests" / "legacy_server"
COMMON = RAIZ / "deploy" / "server" / "common.sh"
APP = "us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app"
DOCS = "us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/docs"

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("flock") and shutil.which("tar")),
    reason="needs bash, flock and tar",
)

DOCKER = r"""#!/bin/bash
# Images are files in $IMAGES named after the reference (the id inside); the registry is
# $REMOTE; the image's /app/deploy is $REPO/deploy, with common.sh's DIR moved to $TESTDIR.
file_of() { echo "$1/$(echo "$2" | tr '/:@' '___')"; }
deploy_copy() {
  local d
  d=$(mktemp -d)
  cp -r "$REPO/deploy/." "$d/"
  sed -i "s#^DIR=/opt/kaladrius#DIR=$TESTDIR#" "$d/server/common.sh"
  echo "$d"
}
case "$1" in
  login) cat >/dev/null ;;
  pull)
    name=${@: -1}
    [ -f "$(file_of "$REMOTE" "$name")" ] || exit 1
    cp "$(file_of "$REMOTE" "$name")" "$(file_of "$IMAGES" "$name")" ;;
  tag) cp "$(file_of "$IMAGES" "$2")" "$(file_of "$IMAGES" "$3")" ;;
  image)
    case "$2" in
      inspect)
        shift 2
        format=""
        if [ "$1" = --format ]; then format=$2; shift 2; fi
        rc=0
        for name in "$@"; do
          f=$(file_of "$IMAGES" "$name")
          if [ ! -f "$f" ]; then rc=1
          elif [[ "$format" == *RepoDigests* ]]; then echo "$name@sha"
          elif [ -n "$format" ]; then cat "$f"; fi
        done
        exit $rc ;;
      rm) rm -f "$(file_of "$IMAGES" "${@: -1}")"; echo "docker image rm ${@: -1}" >>"$CALLS" ;;
      prune) ;;
    esac ;;
  run)
    if [[ "$*" == *"tar -C /app/deploy -cf - ."* ]]; then
      d=$(deploy_copy); tar -C "$d" -cf - .; rm -rf "$d"
    elif [[ "$*" == *"tar -C /app/deploy -cf - docker-compose.prod.yml Caddyfile"* ]]; then
      tar -C "$REPO/deploy" -cf - docker-compose.prod.yml Caddyfile
    else  # run --rm --entrypoint cat IMAGE /app/deploy/<path>
      path=${@: -1}
      d=$(deploy_copy); cat "$d/${path#/app/deploy/}"; rm -rf "$d"
    fi ;;
  compose)
    if [[ "$*" == *" ps "* ]]; then exit 0; fi
    echo "compose ${*:4} with $(cat "$(file_of "$IMAGES" "$APP_IMAGE")")" >>"$CALLS" ;;
  *) echo "fake docker: $*" >&2; exit 2 ;;
esac
"""

CURL = r"""#!/bin/bash
# The health page answers from $ANSWERS, one per line (0 = up), up when it runs out; the
# monitors' signals are recorded; Google's metadata server gives a token.
case "$*" in
  *metadata.google.internal*) echo '{"access_token":"x"}' ;;
  */api/v1/saude*)
    answer=$(head -1 "$ANSWERS" 2>/dev/null || echo 0)
    sed -i 1d "$ANSWERS" 2>/dev/null || true
    exit "${answer:-0}" ;;
  *) echo "curl ${@: -1}" >>"$CALLS" ;;
esac
"""

SYSTEMCTL = r"""#!/bin/bash
echo "systemctl $*" >>"$CALLS"
"""

OLD_UNITS = ("atualizar", "backup", "saude", "restauracao", "demonstracao")
# Run as root, these commands would reach the real Docker: they are compared only when refused.
COMO_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="running as root")


@pytest.fixture
def servidor(tmp_path):
    """A Google Cloud server as 0.54.1 left it, with 0.55's image (B) in the registry."""
    dir_ = tmp_path / "opt"
    for pasta in ("bin", "release/servidor", "imagens", "remoto", "path", "systemd"):
        (dir_ / pasta if pasta in ("bin", "release/servidor") else tmp_path / pasta).mkdir(
            parents=True
        )
    for nome in ("atualizar.sh", "comum.sh"):
        texto = (LEGADO / nome).read_text().replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
        (dir_ / "bin" / nome).write_text(texto)
        (dir_ / "bin" / nome).chmod(0o755)
        # What the previous extractions left in release/servidor (copied again by the old script).
        (dir_ / "release" / "servidor" / nome).write_text(texto)
    for nome in ("saude.sh", "testar_restauracao.sh", "reiniciar_demonstracao.sh"):
        (dir_ / "bin" / nome).write_text("# 0.54.1\n")
        (dir_ / "release" / "servidor" / nome).write_text("# 0.54.1\n")
    (dir_ / ".env").write_text(
        "SITE_HOSTNAME=k.example\n"
        "MONITOR_ATUALIZACAO_URL=http://monitor.test/update\n"
        "MONITOR_SISTEMA_URL=http://monitor.test/system\n"
    )
    (dir_ / "imagem-instalada").write_text("A\nD\n")
    (dir_ / "unidades-antigas").mkdir()  # decision 071's
    systemd = tmp_path / "systemd"
    (systemd / "timers.target.wants").mkdir()
    for unidade in OLD_UNITS:
        for tipo in ("service", "timer"):
            (systemd / f"kaladrius-{unidade}.{tipo}").write_text("[Unit]\n")
        (systemd / "timers.target.wants" / f"kaladrius-{unidade}.timer").symlink_to(
            systemd / f"kaladrius-{unidade}.timer"
        )
    fakes = {"docker": DOCKER, "curl": CURL, "systemctl": SYSTEMCTL}
    for nome, texto in fakes.items():
        (tmp_path / "path" / nome).write_text(texto)
        (tmp_path / "path" / nome).chmod(0o755)

    def imagem(lugar, nome, ident):
        (tmp_path / lugar / nome.replace("/", "_").replace(":", "_")).write_text(ident + "\n")

    for lugar in ("imagens", "remoto"):
        imagem(lugar, f"{APP}:latest", "A")
        imagem(lugar, f"{DOCS}:latest", "D")
    imagem("imagens", f"{APP}:anterior", "A")
    imagem("remoto", f"{APP}:latest", "B")  # 0.55, with the names of decision 147

    class Servidor:
        dir = dir_
        calls = tmp_path / "calls"

        def rodar(self, *comando, respostas=()):
            self.calls.write_text("")
            (tmp_path / "respostas").write_text("".join(f"{r}\n" for r in respostas))
            ambiente = {
                "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
                "IMAGES": str(tmp_path / "imagens"),
                "REMOTE": str(tmp_path / "remoto"),
                "REPO": str(RAIZ),
                "TESTDIR": str(dir_),
                "CALLS": str(self.calls),
                "ANSWERS": str(tmp_path / "respostas"),
                "SYSTEMD_DIR": str(systemd),
                "SAUDE_ESPERA": "0",  # the old name: a failed check is not waited for
            }
            resultado = subprocess.run(  # noqa: S603 (the test's own scripts)
                [shutil.which("bash"), *comando],
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return resultado, self.calls.read_text().splitlines()

        def imagem(self, nome):
            arquivo = tmp_path / "imagens" / nome.replace("/", "_").replace(":", "_")
            return arquivo.read_text().strip() if arquivo.exists() else None

        def ler(self, nome):
            arquivo = dir_ / nome
            return arquivo.read_text().split() if arquivo.exists() else None

    return Servidor()


def assert_nos_nomes_novos(s):
    systemd = s.dir.parent / "systemd"
    for unidade in ("update", "backup", "health", "restore-test", "demo-reset"):
        for tipo in ("service", "timer"):
            assert (systemd / f"kaladrius-{unidade}.{tipo}").is_file(), unidade
    for unidade in ("atualizar", "saude", "restauracao", "demonstracao"):
        assert not (systemd / f"kaladrius-{unidade}.timer").exists()
        assert not os.path.lexists(systemd / "timers.target.wants" / f"kaladrius-{unidade}.timer")
        assert (s.dir / "legacy" / "units" / f"kaladrius-{unidade}.timer").is_file()
    assert not (s.dir / "unidades-antigas").exists()
    for script in ("update.sh", "common.sh", "backup.sh", "health.sh", "test_restore.sh"):
        assert (s.dir / "bin" / script).is_file(), script
    for antigo in ("comum.sh", "saude.sh", "testar_restauracao.sh", "reiniciar_demonstracao.sh"):
        assert not (s.dir / "bin" / antigo).exists(), antigo
        assert (s.dir / "legacy" / "bin" / antigo).is_file(), antigo
    # The VM's old startup script runs bin/atualizar.sh: now a pointer to update.sh.
    assert "update.sh" in (s.dir / "bin" / "atualizar.sh").read_text()
    env = (s.dir / ".env").read_text()
    assert "MONITOR_UPDATE_URL=http://monitor.test/update\n" in env
    assert "MONITOR_SYSTEM_URL=http://monitor.test/system\n" in env
    assert "ATUALIZACAO" not in env and "SISTEMA" not in env
    assert "MONITOR_ATUALIZACAO_URL" in (s.dir / ".env.before-147").read_text()
    assert oct((s.dir / ".env.before-147").stat().st_mode & 0o777) == "0o600"
    assert not (s.dir / "imagem-instalada").exists()


def test_a_primeira_atualizacao_feita_pelo_atualizar_antigo(servidor):
    resultado, calls = servidor.rodar(str(servidor.dir / "bin" / "atualizar.sh"))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "compose up -d --remove-orphans with B" in calls
    assert servidor.ler("installed-image") == ["B", "D"]
    assert servidor.imagem(f"{APP}:previous") == "B"
    assert servidor.imagem(f"{APP}:anterior") is None
    assert_nos_nomes_novos(servidor)
    assert any(c.startswith("systemctl enable --now kaladrius-update.timer") for c in calls)
    assert "systemctl stop kaladrius-atualizar.timer" in calls
    # The old script's signal, by its old name, reaches the monitor of the migrated .env.
    assert calls[-1] == "curl http://monitor.test/update"

    # From then on the new update.sh runs: nothing new, nothing restarted.
    resultado, calls = servidor.rodar(str(servidor.dir / "bin" / "update.sh"))
    assert resultado.returncode == 0, resultado.stderr
    assert not [c for c in calls if c.startswith("compose")]
    assert calls[-1] == "curl http://monitor.test/update"

    # And the pointer the VM's old startup script runs, with its old option.
    resultado, calls = servidor.rodar(str(servidor.dir / "bin" / "atualizar.sh"), "--forcar")
    assert resultado.returncode == 0, resultado.stderr
    assert "compose up -d --remove-orphans with B" in calls


def test_a_versao_nova_que_nao_sobe_volta_a_anterior_com_os_nomes_novos(servidor):
    # B does not answer; A, put back, does.
    resultado, calls = servidor.rodar(str(servidor.dir / "bin" / "atualizar.sh"), respostas=(1, 0))
    assert resultado.returncode == 1
    subidas = [c for c in calls if c.startswith("compose up")]
    assert subidas == [
        "compose up -d --remove-orphans with B",
        "compose up -d --remove-orphans with A",
    ]
    assert servidor.ler("refused-image") == ["B", "D"]
    assert servidor.ler("installed-image") == ["A", "D"]
    assert servidor.imagem(f"{APP}:previous") == "A"
    assert "curl http://monitor.test/update/fail" in calls
    assert_nos_nomes_novos(servidor)

    # The new update.sh keeps the refusal.
    resultado, calls = servidor.rodar(str(servidor.dir / "bin" / "update.sh"))
    assert resultado.returncode == 0, resultado.stderr
    assert not [c for c in calls if c.startswith("compose")]
    assert calls[-1] == "curl http://monitor.test/update/fail"


def test_o_startup_script_antigo_da_vm(servidor, tmp_path):
    # The end of 0.54.1's instalar.sh, as the VM runs it on every boot, image already pulled.
    instalar = (LEGADO / "instalar.sh").read_text()
    final = instalar[instalar.index("# The rest of the deploy files") :]
    script = tmp_path / "boot.sh"
    script.write_text(
        f'set -euo pipefail\nDIR="{servidor.dir}"\nIMAGEM_APP="{APP}:latest"\ndocker pull -q '
        f'"$IMAGEM_APP" >/dev/null\n{final}'
    )
    resultado, calls = servidor.rodar(str(script))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "compose up -d --remove-orphans with B" in calls
    assert servidor.ler("installed-image") == ["B", "D"]
    assert_nos_nomes_novos(servidor)


def comum(tmp_path, env):
    dir_ = tmp_path / "opt"
    (dir_ / "release").mkdir(parents=True)
    texto = COMMON.read_text().replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
    (dir_ / "common.sh").write_text(texto)
    (dir_ / ".env").write_text(env)
    return dir_


def avaliar(dir_, expressao, ambiente=None):
    resultado = subprocess.run(  # noqa: S603 (the test's own script)
        [shutil.which("bash"), "-c", f'source "{dir_}/common.sh"; {expressao}'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(ambiente or {})},
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.strip()


def test_env_value_le_os_dois_nomes(tmp_path):
    antigo = comum(tmp_path / "a", "KALADRIUS_BACKUP_DIAS=7\nMONITOR_ATUALIZACAO_URL=u\n")
    # A .env of 0.54, not migrated yet, read by the new names.
    assert avaliar(antigo, "env_value KALADRIUS_BACKUP_DAYS") == "7"
    assert avaliar(antigo, "env_value MONITOR_UPDATE_URL") == "u"
    novo = comum(tmp_path / "b", "KALADRIUS_BACKUP_DAYS=9\nMONITOR_UPDATE_URL=v\n")
    # A migrated .env, read by the old names (the scripts of 0.54 during the first update).
    assert avaliar(novo, "env_value KALADRIUS_BACKUP_DIAS") == "9"
    assert avaliar(novo, "env_value MONITOR_ATUALIZACAO_URL") == "v"
    assert avaliar(novo, "env_value SITE_HOSTNAME") == ""


def test_migrar_o_env_so_troca_os_nomes(tmp_path):
    env = (
        "# a comment\nDJANGO_SECRET_KEY=x=y\nKALADRIUS_ACESSO=rede-interna\n"
        "KALADRIUS_BACKUP_PASTA=/srv/b\nSITE_HOSTNAME=192.168.0.10\nIMAGEM_APP=k:1\n"
    )
    dir_ = comum(tmp_path, env)
    sistema = tmp_path / "systemd"
    sistema.mkdir()
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert (dir_ / ".env").read_text() == (
        "# a comment\nDJANGO_SECRET_KEY=x=y\nKALADRIUS_ACCESS=internal-network\n"
        "KALADRIUS_BACKUP_DIR=/srv/b\nSITE_HOSTNAME=192.168.0.10\nAPP_IMAGE=k:1\n"
    )
    assert (dir_ / ".env.before-147").read_text() == env
    # Again: nothing changes, and the copy of the original stays.
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert (dir_ / ".env.before-147").read_text() == env


def test_migrar_os_arquivos_de_estado(tmp_path):
    dir_ = comum(tmp_path, "")
    for nome in ("admin-criado", "sem-repositorio", "imagem-recusada"):
        (dir_ / nome).write_text(nome)
    (dir_ / "demonstracao").mkdir()
    (dir_ / "demonstracao" / "base-data").write_text("2026-10-30")
    (dir_ / "anterior").mkdir()
    (dir_ / "installed-image").write_text("ja-novo")  # never overwritten by an old one
    (dir_ / "imagem-instalada").write_text("velho")
    sistema = tmp_path / "systemd"
    sistema.mkdir()
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert (dir_ / "admin-created").read_text() == "admin-criado"
    assert (dir_ / "no-repository").is_file()
    assert (dir_ / "refused-image").is_file()
    assert (dir_ / "demo" / "base-date").read_text() == "2026-10-30"
    assert (dir_ / "previous").is_dir()
    assert (dir_ / "installed-image").read_text() == "ja-novo"


def test_o_pacote_antigo_atualizado_migra_antes_de_decidir(tmp_path):
    # A clinic's 0.54 package updated to this one: admin-criado is read as admin-created, so the
    # update starts the system instead of asking the setup questions again; the timers of the
    # old package, whose unit files the package manager already removed, leave no links behind.
    from tests.test_linux_package import depois_de_instalar

    dir_ = tmp_path / "opt"
    dir_.mkdir()
    (dir_ / "admin-criado").write_text("")
    (dir_ / ".env").write_text("SITE_HOSTNAME=192.168.0.10\nKALADRIUS_ACESSO=rede-interna\n")
    links = tmp_path / "systemd" / "timers.target.wants"
    links.mkdir(parents=True)
    for unidade in ("saude", "restauracao"):
        (links / f"kaladrius-{unidade}.timer").symlink_to(
            f"/usr/lib/systemd/system/kaladrius-{unidade}.timer"
        )
    _saida, chamadas = depois_de_instalar(tmp_path, "configure", admin_criado=False)
    assert "update.sh --force" in chamadas
    assert (dir_ / "admin-created").exists()
    assert "KALADRIUS_ACCESS=internal-network" in (dir_ / ".env").read_text()
    assert not list(links.iterdir())
    assert "systemctl disable kaladrius-saude.timer" in chamadas
    # Their service files already gone, the old timers fail on the reload: that state goes.
    assert (
        "systemctl reset-failed kaladrius-saude.timer kaladrius-saude.service "
        "kaladrius-restauracao.timer kaladrius-restauracao.service" in chamadas
    )


@pytest.mark.parametrize(
    ("antigo", "novo"),
    [
        ("versao", "version"),
        ("ajuda", "help"),
        pytest.param("estado", "status", marks=COMO_ROOT),
        pytest.param("parar", "stop", marks=COMO_ROOT),
        pytest.param("testar-restauracao", "test-restore", marks=COMO_ROOT),
    ],
)
def test_os_comandos_antigos_ainda_funcionam(tmp_path, antigo, novo):
    from tests.test_linux_package import kaladrius

    for pasta in ("a", "b"):
        (tmp_path / pasta).mkdir()
    a = kaladrius(tmp_path / "a", antigo)
    b = kaladrius(tmp_path / "b", novo)
    assert (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr)
