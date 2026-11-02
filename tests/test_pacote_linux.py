"""The Linux package (.deb and .rpm, decision 140): what deploy/pacote/nfpm.yaml ships, the
package mode of deploy/servidor/comum.sh, and the `kaladrius` command. The installation itself
(apt and dnf, the text screens, backups, the restore test, an update and its rollback) is tested
for real in a clean virtual machine before each change; see deploy/pacote/README.md."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "deploy" / "pacote"
SERVIDOR = RAIZ / "deploy" / "servidor"
NFPM = (PACOTE / "nfpm.yaml").read_text()

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")


def conteudo():
    """The (src, dst) pairs of the package's contents."""
    return re.findall(r"- src: (\S+)\n\s+dst: (\S+)", NFPM)


def test_todo_arquivo_do_pacote_existe():
    for origem, _destino in conteudo():
        if (
            origem.startswith("/") or origem == "dist/pacote-linux"
        ):  # a symlink; written by gerar.sh
            continue
        assert (RAIZ / origem).is_file(), origem
    for script in re.findall(r"(?:postinstall|preremove|postremove): (\S+)", NFPM):
        assert (RAIZ / script).is_file(), script


def test_cada_tarefa_agendada_roda_um_script_do_pacote():
    destinos = {destino for _origem, destino in conteudo()}
    unidades = [d for d in destinos if d.startswith("/usr/lib/systemd/system/")]
    assert {Path(u).name for u in unidades} == {
        f"kaladrius-{nome}.{tipo}"
        for nome in ("backup", "saude", "restauracao")
        for tipo in ("service", "timer")
    }
    for unidade in unidades:
        if unidade.endswith(".service"):
            texto = (SERVIDOR / Path(unidade).name).read_text()
            executavel = re.search(r"^ExecStart=(\S+)", texto, re.M).group(1)
            assert executavel in destinos, (unidade, executavel)


def test_o_pacote_liga_as_tarefas_que_traz():
    comum = (SERVIDOR / "comum.sh").read_text()
    bloco = comum.split("if instalado_por_pacote; then  # its units came with the package")[1]
    ligadas = set(re.findall(r"kaladrius-[a-z]+\.timer", bloco.split("return 0")[0]))
    trazidas = {Path(d).name for _o, d in conteudo() if d.endswith(".timer")}
    assert ligadas == trazidas


def comum_em(pasta, pacote=None, env=""):
    """comum.sh with its DIR in a temporary folder."""
    (pasta / "release").mkdir(parents=True, exist_ok=True)
    texto = (SERVIDOR / "comum.sh").read_text().replace("DIR=/opt/kaladrius", f"DIR={pasta}", 1)
    (pasta / "comum.sh").write_text(texto)
    if pacote is not None:
        (pasta / "release" / "pacote-linux").write_text(pacote)
    (pasta / ".env").write_text(env)
    return pasta / "comum.sh"


def avaliar(comum, expressao, ambiente=None):
    resultado = subprocess.run(  # noqa: S603 (the test's own script)
        [BASH, "-c", f'source "{comum}"; {expressao}'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(ambiente or {})},
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.strip()


IMAGEM = "ghcr.io/facchini-miguel/kaladrius:0.54.0@sha256:abc"


def test_modo_pacote_usa_a_imagem_fixada_por_digest(tmp_path):
    comum = comum_em(tmp_path, pacote=f"VERSAO=0.54.0\nIMAGEM={IMAGEM}\n")
    assert avaliar(comum, 'echo "$IMAGEM_APP|$IMAGEM_DOCS|$VERSAO_DO_PACOTE|$REGISTRO"') == (
        f"{IMAGEM}||0.54.0|ghcr.io"
    )
    assert avaliar(comum, 'echo "$IMAGEM_APP_ANTERIOR"') == (
        "ghcr.io/facchini-miguel/kaladrius:anterior"
    )
    # No registry login: the image is public.
    assert avaliar(comum, "entrar_no_registro && echo sem-login") == "sem-login"


def test_modo_pacote_aceita_outra_imagem(tmp_path):
    comum = comum_em(
        tmp_path, pacote=f"VERSAO=0.54.0\nIMAGEM={IMAGEM}\n", env="KALADRIUS_IMAGEM=k:teste\n"
    )
    assert avaliar(comum, 'echo "$IMAGEM_APP $IMAGEM_APP_ANTERIOR"') == "k:teste k:anterior"
    assert avaliar(comum, 'echo "$IMAGEM_APP"', {"KALADRIUS_IMAGEM": "outra:1"}) == "outra:1"


def test_sem_pacote_segue_o_google_cloud(tmp_path):
    comum = comum_em(tmp_path)
    # Google Cloud copies the whole deploy/ folder of the image to release/, the package's
    # sources included: they must not switch on the package mode.
    shutil.copytree(PACOTE, tmp_path / "release" / "pacote")
    app, docs, anterior = avaliar(
        comum, 'echo "$IMAGEM_APP $IMAGEM_DOCS $IMAGEM_APP_ANTERIOR"'
    ).split()
    assert app.endswith("/kaladrius/app:latest") and docs.endswith("/kaladrius/docs:latest")
    assert anterior.endswith("/kaladrius/app:anterior")


@pytest.mark.parametrize(
    ("referencia", "repositorio"),
    [
        ("ghcr.io/a/b:1.0@sha256:abc", "ghcr.io/a/b"),
        ("us-east1-docker.pkg.dev/p/k/app:latest", "us-east1-docker.pkg.dev/p/k/app"),
        ("localhost:5000/x", "localhost:5000/x"),
        ("localhost:5000/x:2", "localhost:5000/x"),
        ("kaladrius:teste", "kaladrius"),
    ],
)
def test_repositorio_de(tmp_path, referencia, repositorio):
    assert avaliar(comum_em(tmp_path), f'repositorio_de "{referencia}"') == repositorio


@pytest.mark.parametrize(("acesso", "esperado"), [("rede-interna", "sim"), ("internet", "nao")])
def test_rede_interna(tmp_path, acesso, esperado):
    comum = comum_em(tmp_path, env=f"KALADRIUS_ACESSO={acesso}\n")
    assert avaliar(comum, "rede_interna && echo sim || echo nao") == esperado


def kaladrius(tmp_path, *args, idioma="C"):
    """The `kaladrius` command as installed: beside comum.sh, here with DIR in tmp_path."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACOTE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(comum_em(tmp_path), bin_ / "comum.sh")
    return subprocess.run(  # noqa: S603 (the package's own command)
        [BASH, str(bin_ / "kaladrius"), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": idioma},
        timeout=30,
    )


@pytest.mark.parametrize(
    ("idioma", "trecho"),
    [
        ("pt_BR.UTF-8", "faz um backup agora"),
        ("es_ES.UTF-8", "hace una copia de seguridad ahora"),
        ("en_US.UTF-8", "makes a backup now"),
        ("C", "makes a backup now"),
    ],
)
def test_ajuda_no_idioma_do_servidor(tmp_path, idioma, trecho):
    resultado = kaladrius(tmp_path, "ajuda", idioma=idioma)
    assert resultado.returncode == 0, resultado.stderr
    assert trecho in resultado.stdout
    assert "sudo kaladrius configurar" in resultado.stdout


@pytest.mark.parametrize("comando", ["ayuda", "help", "--help"])
def test_ajuda_em_outros_nomes(tmp_path, comando):
    assert kaladrius(tmp_path, comando).returncode == 0


def test_comando_desconhecido_falha(tmp_path):
    assert kaladrius(tmp_path, "nao-existe").returncode == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="running as root")
def test_configurar_exige_root(tmp_path):
    resultado = kaladrius(tmp_path, "configurar", "--acesso", "rede-interna")
    assert resultado.returncode == 1
    assert "sudo kaladrius configurar" in resultado.stderr


def test_nenhum_script_confere_duas_condicoes_numa_linha_so():
    # `[ a ] && [ b ]` alone on a line does not stop a `set -e` script when `a` fails: the
    # restore test passed with no clinic restored until decision 140.
    padrao = re.compile(r"^\s*\[[^]]*\]\s*&&\s*\[[^]]*\]\s*$")
    for script in [*SERVIDOR.glob("*.sh"), *PACOTE.glob("*.sh"), PACOTE / "kaladrius"]:
        for numero, linha in enumerate(script.read_text().splitlines(), 1):
            assert not padrao.match(linha), f"{script.name}:{numero}: {linha.strip()}"


def test_caddy_nunca_recebe_o_endereco_da_documentacao_vazio():
    # An empty address makes the Caddyfile's docs block invalid and Caddy does not start.
    compose = (RAIZ / "deploy" / "docker-compose.prod.yml").read_text()
    assert "DOCS_HOSTNAME: ${DOCS_HOSTNAME:-docs.localhost}" in compose


def test_remover_o_pacote_nunca_apaga_os_dados():
    # The database, the backups and the .env stay; the help printed after a removal shows the
    # commands, for a person to decide (indented lines of the message).
    for script in ("antes_de_remover.sh", "depois_de_remover.sh"):
        for linha in (PACOTE / script).read_text().splitlines():
            if linha.lstrip().startswith("#") or linha.startswith("    sudo "):
                continue
            assert "volume rm" not in linha and "down -v" not in linha, linha
            if re.search(r"\brm\b", linha):
                assert linha.strip() == "rm -f /opt/kaladrius/release/.env", linha
