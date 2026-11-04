"""Automatic rollback of the server update (decision 135): deploy/server/update.sh run with
a fake `docker` and the helpers of common.sh replaced, so no container, registry or network is
touched. Each image is a file holding its id; `docker pull` takes the id the registry has."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
UPDATE = RAIZ / "deploy" / "server" / "update.sh"

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
def servidor(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for pasta in ("imagens", "remoto", "path"):
        (tmp_path / pasta).mkdir()
    shutil.copy(UPDATE, bin_ / "update.sh")
    (bin_ / "common.sh").write_text(textwrap.dedent(COMMON.format(dir=tmp_path)))
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER)
    docker.chmod(0o755)
    (tmp_path / ".env").write_text("SITE_HOSTNAME=exemplo.test\n")

    class Servidor:
        dir = tmp_path

        def imagem(self, lugar, name, ident):
            (tmp_path / lugar / name.replace("/", "_").replace(":", "_")).write_text(ident + "\n")

        def id_local(self, name):
            arquivo = tmp_path / "imagens" / name.replace("/", "_").replace(":", "_")
            return arquivo.read_text().strip() if arquivo.exists() else None

        def saude(self, *respostas):
            (tmp_path / "saude").write_text("".join(f"{r}\n" for r in respostas))

        def rodar(self, *args):
            (tmp_path / "log").write_text("")
            ambiente = {
                "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
                "IMAGENS": str(tmp_path / "imagens"),
                "REMOTO": str(tmp_path / "remoto"),
            }
            resultado = subprocess.run(  # noqa: S603 (the test's own script and arguments)
                [shutil.which("bash"), str(bin_ / "update.sh"), *args],
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return resultado.returncode, (tmp_path / "log").read_text().splitlines()

        def ler(self, name):
            arquivo = tmp_path / name
            return arquivo.read_text().split() if arquivo.exists() else None

    s = Servidor()
    # Installed and running: app A and docs D; the registry has the same.
    for lugar in ("imagens", "remoto"):
        s.imagem(lugar, "registro/app:latest", "A")
        s.imagem(lugar, "registro/docs:latest", "D")
    s.imagem("imagens", "registro/app:previous", "A")
    (tmp_path / "installed-image").write_text("A\nD\n")
    return s


def test_sem_versao_nova_nada_muda(servidor):
    code, log = servidor.rodar()
    assert code == 0
    assert log == ["monitor MONITOR_UPDATE_URL ok"]


def test_versao_nova_que_sobe_vira_a_anterior_da_proxima(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(0)
    code, log = servidor.rodar()
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert servidor.ler("installed-image") == ["B", "D"]
    assert servidor.id_local("registro/app:previous") == "B"
    assert log[-1] == "monitor MONITOR_UPDATE_URL ok"
    # Pulled by digest (the Linux package), the image :previous named is never "dangling":
    # removed by id, the docs image still in use kept.
    assert servidor.ler("removidas") == ["A"]


def test_versao_nova_que_nao_sobe_volta_a_anterior_e_fica_recusada(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)  # B does not answer; A answers again
    code, log = servidor.rodar()
    assert code == 1
    subidas = [linha for linha in log if linha.startswith("compose up")]
    assert subidas == [
        "compose up -d --remove-orphans com B",
        "compose up -d --remove-orphans com A",
    ]
    # A's own Compose file and Caddyfile go back first: they name the Caddy and PostgreSQL
    # digests (decision 138), so a broken one of B is undone too; then Caddy reloads.
    volta = log.index("compose up -d --remove-orphans com A")
    assert log[volta - 1] == "compose de A"
    assert log[volta + 1] == "caddy"
    assert servidor.ler("installed-image") == ["A", "D"]  # still the last good one
    assert servidor.ler("refused-image") == ["B", "D"]
    assert servidor.id_local("registro/app:previous") == "A"
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"

    # Next runs: the refused version is not tried again, and the monitor stays red.
    code, log = servidor.rodar()
    assert code == 0
    assert not any(linha.startswith("compose") for linha in log)
    assert log == ["monitor MONITOR_UPDATE_URL fail"]

    # A newer version is tried, and once it comes up the refusal is gone.
    servidor.imagem("remoto", "registro/app:latest", "C")
    servidor.saude(0)
    code, log = servidor.rodar()
    assert code == 0
    assert "compose up -d --remove-orphans com C" in log
    assert servidor.ler("installed-image") == ["C", "D"]
    assert servidor.ler("refused-image") is None
    assert servidor.ler("removidas") == ["A", "B"]  # the old :previous and the refused one


def test_duas_versoes_recusadas_seguidas_nao_ficam_no_disco(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)
    servidor.rodar()
    # C refused too: B is not needed any more, and only the latest refusal is kept.
    servidor.imagem("remoto", "registro/app:latest", "C")
    servidor.saude(1, 0)
    code, _log = servidor.rodar()
    assert code == 1
    assert servidor.ler("refused-image") == ["C", "D"]
    assert servidor.ler("removidas") == ["B"]  # never A (running again) or D (in use)
    servidor.imagem("remoto", "registro/app:latest", "E")
    servidor.saude(0)
    code, _log = servidor.rodar()
    assert code == 0
    assert servidor.ler("removidas") == ["B", "A", "C"]


def test_forcar_tenta_de_novo_a_versao_recusada(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)
    servidor.rodar()
    servidor.saude(0)
    code, log = servidor.rodar("--force")
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert servidor.ler("installed-image") == ["B", "D"]


def test_servidor_antigo_guarda_a_anterior_na_primeira_execucao(servidor):
    (servidor.dir / "imagens" / "registro_app_previous").unlink()
    code, _log = servidor.rodar()
    assert code == 0
    assert servidor.id_local("registro/app:previous") == "A"


def test_sem_anterior_guardada_avisa_e_nao_finge_que_voltou(servidor):
    (servidor.dir / "imagens" / "registro_app_previous").unlink()
    (servidor.dir / "installed-image").write_text("X\nD\n")  # A was never confirmed
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1)
    code, log = servidor.rodar()
    assert code == 1
    assert [linha for linha in log if linha.startswith("compose up")] == [
        "compose up -d --remove-orphans com B"
    ]
    assert servidor.ler("refused-image") == ["B", "D"]
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"


def test_pacote_linux_sem_documentacao_e_com_imagem_so_local(servidor):
    # Installed from the Linux package (decision 140): no docs image, and an image already on
    # the server is enough when the registry does not have it (a test image, no internet).
    common = servidor.dir / "bin" / "common.sh"
    common.write_text(
        common.read_text().replace('DOCS_IMAGE="registro/docs:latest"', 'DOCS_IMAGE=""')
    )
    (servidor.dir / "linux-package").write_text("VERSION=0.54.0\n")
    (servidor.dir / "installed-image").write_text("A\n")
    servidor.imagem("imagens", "registro/app:latest", "B")
    (servidor.dir / "remoto" / "registro_app_latest").unlink()
    code, log = servidor.rodar()
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
    assert servidor.ler("installed-image") == ["B"]


def test_google_cloud_sem_o_registro_falha_e_avisa(servidor):
    # Only the Linux package goes on with the image already on the server: on Google Cloud the
    # update monitor reports a registry it cannot reach.
    (servidor.dir / "remoto" / "registro_app_latest").unlink()
    code, log = servidor.rodar()
    assert code == 1
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"


def test_pacote_sem_a_imagem_no_registro_nem_no_servidor_falha_e_avisa(servidor):
    (servidor.dir / "linux-package").write_text("VERSION=0.54.0\n")
    for lugar in ("imagens", "remoto"):
        (servidor.dir / lugar / "registro_app_latest").unlink()
    code, log = servidor.rodar()
    assert code == 1
    assert log[-1] == "monitor MONITOR_UPDATE_URL fail"
    assert not [linha for linha in log if linha.startswith("compose")]


def test_o_nome_antigo_de_force_ainda_vale(servidor):
    # The VM's startup script of a server created before decision 147 still says --forcar.
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)
    servidor.rodar()
    servidor.saude(0)
    code, log = servidor.rodar("--forcar")
    assert code == 0
    assert "compose up -d --remove-orphans com B" in log
