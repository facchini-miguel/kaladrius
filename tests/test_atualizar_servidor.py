"""Automatic rollback of the server update (decision 135): deploy/servidor/atualizar.sh run with
a fake `docker` and the helpers of comum.sh replaced, so no container, registry or network is
touched. Each image is a file holding its id; `docker pull` takes the id the registry has."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ATUALIZAR = RAIZ / "deploy" / "servidor" / "atualizar.sh"

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
  *) echo "docker falso: $*" >&2; exit 2 ;;
esac
"""

COMUM = r"""
DIR="{dir}"
IMAGEM_APP="registro/app:latest"
IMAGEM_DOCS="registro/docs:latest"
IMAGEM_INSTALADA="$DIR/imagem-instalada"
IMAGEM_APP_ANTERIOR="registro/app:anterior"
IMAGEM_RECUSADA="$DIR/imagem-recusada"
export IMAGEM_APP IMAGEM_DOCS
log() {{ echo "$*" >> "$DIR/log"; }}
entrar_no_registro() {{ :; }}
extrair_arquivos_de_deploy() {{ log "extrair $IMAGEM_APP"; }}
instalar_agendamentos() {{ log agendamentos; }}
compose() {{ log "compose $* com $(cat "$IMAGENS/$(echo "$IMAGEM_APP" | tr '/:' '__')")"; }}
restaurar_compose_de() {{ log "compose de $(cat "$IMAGENS/$(echo "$1" | tr '/:' '__')")"; }}
recarregar_caddy() {{ log caddy; }}
avisar_monitor() {{ log "monitor $1 ${{2:-ok}}"; }}
# Answers from $DIR/saude, one per line (0 = up, 1 = down); up when it runs out.
sistema_no_ar() {{
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
    shutil.copy(ATUALIZAR, bin_ / "atualizar.sh")
    (bin_ / "comum.sh").write_text(textwrap.dedent(COMUM.format(dir=tmp_path)))
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER)
    docker.chmod(0o755)
    (tmp_path / ".env").write_text("SITE_HOSTNAME=exemplo.test\n")

    class Servidor:
        dir = tmp_path

        def imagem(self, lugar, nome, ident):
            (tmp_path / lugar / nome.replace("/", "_").replace(":", "_")).write_text(ident + "\n")

        def id_local(self, nome):
            arquivo = tmp_path / "imagens" / nome.replace("/", "_").replace(":", "_")
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
                [shutil.which("bash"), str(bin_ / "atualizar.sh"), *args],
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return resultado.returncode, (tmp_path / "log").read_text().splitlines()

        def ler(self, nome):
            arquivo = tmp_path / nome
            return arquivo.read_text().split() if arquivo.exists() else None

    s = Servidor()
    # Installed and running: app A and docs D; the registry has the same.
    for lugar in ("imagens", "remoto"):
        s.imagem(lugar, "registro/app:latest", "A")
        s.imagem(lugar, "registro/docs:latest", "D")
    s.imagem("imagens", "registro/app:anterior", "A")
    (tmp_path / "imagem-instalada").write_text("A\nD\n")
    return s


def test_sem_versao_nova_nada_muda(servidor):
    codigo, log = servidor.rodar()
    assert codigo == 0
    assert log == ["monitor MONITOR_ATUALIZACAO_URL ok"]


def test_versao_nova_que_sobe_vira_a_anterior_da_proxima(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(0)
    codigo, log = servidor.rodar()
    assert codigo == 0
    assert "compose up -d --remove-orphans com B" in log
    assert servidor.ler("imagem-instalada") == ["B", "D"]
    assert servidor.id_local("registro/app:anterior") == "B"
    assert log[-1] == "monitor MONITOR_ATUALIZACAO_URL ok"


def test_versao_nova_que_nao_sobe_volta_a_anterior_e_fica_recusada(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)  # B does not answer; A answers again
    codigo, log = servidor.rodar()
    assert codigo == 1
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
    assert servidor.ler("imagem-instalada") == ["A", "D"]  # still the last good one
    assert servidor.ler("imagem-recusada") == ["B", "D"]
    assert servidor.id_local("registro/app:anterior") == "A"
    assert log[-1] == "monitor MONITOR_ATUALIZACAO_URL fail"

    # Next runs: the refused version is not tried again, and the monitor stays red.
    codigo, log = servidor.rodar()
    assert codigo == 0
    assert not any(linha.startswith("compose") for linha in log)
    assert log == ["monitor MONITOR_ATUALIZACAO_URL fail"]

    # A newer version is tried, and once it comes up the refusal is gone.
    servidor.imagem("remoto", "registro/app:latest", "C")
    servidor.saude(0)
    codigo, log = servidor.rodar()
    assert codigo == 0
    assert "compose up -d --remove-orphans com C" in log
    assert servidor.ler("imagem-instalada") == ["C", "D"]
    assert servidor.ler("imagem-recusada") is None


def test_forcar_tenta_de_novo_a_versao_recusada(servidor):
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1, 0)
    servidor.rodar()
    servidor.saude(0)
    codigo, log = servidor.rodar("--forcar")
    assert codigo == 0
    assert "compose up -d --remove-orphans com B" in log
    assert servidor.ler("imagem-instalada") == ["B", "D"]


def test_servidor_antigo_guarda_a_anterior_na_primeira_execucao(servidor):
    (servidor.dir / "imagens" / "registro_app_anterior").unlink()
    codigo, _log = servidor.rodar()
    assert codigo == 0
    assert servidor.id_local("registro/app:anterior") == "A"


def test_sem_anterior_guardada_avisa_e_nao_finge_que_voltou(servidor):
    (servidor.dir / "imagens" / "registro_app_anterior").unlink()
    (servidor.dir / "imagem-instalada").write_text("X\nD\n")  # A was never confirmed
    servidor.imagem("remoto", "registro/app:latest", "B")
    servidor.saude(1)
    codigo, log = servidor.rodar()
    assert codigo == 1
    assert [linha for linha in log if linha.startswith("compose up")] == [
        "compose up -d --remove-orphans com B"
    ]
    assert servidor.ler("imagem-recusada") == ["B", "D"]
    assert log[-1] == "monitor MONITOR_ATUALIZACAO_URL fail"
