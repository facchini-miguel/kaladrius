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
    for script in re.findall(r"(?:postinstall|postupgrade|preremove|postremove): (\S+)", NFPM):
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
    # Also when the package is installed again over a configured installation, before the
    # system is started: a removal disabled them, and the new version may not come up.
    instalar = (PACOTE / "depois_de_instalar.sh").read_text().split('if [ -f "$DIR/.env" ]')[1]
    antes_de_subir = instalar.split('"$DIR/bin/atualizar.sh"')[0]
    assert set(re.findall(r"kaladrius-[a-z]+\.timer", antes_de_subir)) == trazidas


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


def test_nenhum_script_usa_grep_q_depois_de_um_cano():
    # With pipefail, `cmd | grep -q x` fails when grep exits at the first match and `cmd` dies
    # writing the rest (SIGPIPE): Kaladrius's own Caddy was taken for another program on 80/443.
    padrao = re.compile(r"\|\s*grep\s+-[a-zA-Z]*q")
    for script in [*SERVIDOR.glob("*.sh"), *PACOTE.glob("*.sh"), PACOTE / "kaladrius"]:
        for numero, linha in enumerate(script.read_text().splitlines(), 1):
            assert not padrao.search(linha), f"{script.name}:{numero}: {linha.strip()}"


@pytest.mark.parametrize(
    ("endereco", "valido"),
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
def test_eh_ipv4(tmp_path, endereco, valido):
    resultado = funcao_do_comando(
        tmp_path, f'eh_ipv4 "{endereco}" && echo sim || echo nao', {"PATH": "/usr/bin:/bin"}
    )
    assert resultado.stdout.strip() == ("sim" if valido else "nao"), resultado.stderr


def test_configurar_de_novo_grava_o_novo_usuario_do_administrador(tmp_path):
    # A first run that did not finish wrote .env; the user name typed on the next run is the
    # one created, so .env (read by `kaladrius senha`) must say the same.
    expressao = (
        'rm "$DIR/.env"; escrever_env rede-interna 192.168.0.10 admin a@x.test; '
        'escrever_env rede-interna 192.168.0.11 suporte ""; '
        'grep -c DJANGO_SECRET_KEY "$DIR/.env"; valor_do_env DJANGO_ADMIN_USERNAME; '
        "valor_do_env DJANGO_ADMIN_EMAIL; valor_do_env SITE_HOSTNAME"
    )
    resultado = funcao_do_comando(tmp_path, expressao, {"PATH": "/usr/bin:/bin"})
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.splitlines() == ["1", "suporte", "", "192.168.0.11"]


def test_pasta_dos_backups(tmp_path):
    assert avaliar(comum_em(tmp_path / "a"), "pasta_dos_backups") == "/var/backups/kaladrius"
    outra = comum_em(tmp_path / "b", env="KALADRIUS_BACKUP_PASTA=/srv/copias\n")
    assert avaliar(outra, "pasta_dos_backups") == "/srv/copias"


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


def test_o_site_e_conferido_pelo_proprio_servidor(tmp_path):
    # A clinic's router often has no "hairpin NAT": from inside, the clinic's public address
    # never answers, and a good new version would be refused.
    pacote = f"VERSAO=0.54.0\nIMAGEM={IMAGEM}\n"
    expressao = 'opcoes_para_o_site k.example; echo "${OPCOES_CURL[*]}"'
    internet = comum_em(tmp_path / "a", pacote=pacote, env="KALADRIUS_ACESSO=internet\n")
    assert avaliar(internet, expressao) == "--resolve k.example:443:127.0.0.1"
    interna = comum_em(tmp_path / "b", pacote=pacote, env="KALADRIUS_ACESSO=rede-interna\n")
    assert avaliar(interna, expressao) == "--insecure"
    # Google Cloud: through the internet, like anyone.
    assert avaliar(comum_em(tmp_path / "c"), expressao) == ""


DOCKER_FALSO = """#!/bin/bash
# docker image inspect [--format F] IMAGE: the id in $IMAGENS/<image>, or a failure.
[ "$1 $2" = "image inspect" ] || exit 2
nome=${@: -1}
arquivo="$IMAGENS/$(echo "$nome" | tr '/:@' '___')"
[ -f "$arquivo" ] || exit 1
[ "$3" = "--format" ] && cat "$arquivo"
exit 0
"""


def comum_com_imagens(tmp_path, imagens, recusada=None):
    """comum.sh in package mode, with a fake `docker` that knows only `imagens` (name: id)."""
    comum = comum_em(tmp_path, pacote="VERSAO=0.55.0\nIMAGEM=kaladrius:nova\n")
    (tmp_path / "imagens").mkdir()
    for nome, ident in imagens.items():
        (tmp_path / "imagens" / nome.replace(":", "_")).write_text(ident)
    (tmp_path / "path").mkdir()
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER_FALSO)
    docker.chmod(0o755)
    if recusada is not None:
        (tmp_path / "imagem-recusada").write_text(recusada + "\n")
    ambiente = {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin", "IMAGENS": str(tmp_path / "imagens")}
    return comum, ambiente


# Decided by comum.sh itself, for every script that sources it.
VERSAO_NO_AR = 'echo "$IMAGEM_APP $COMPOSE_ARQUIVO"'


def test_depois_de_um_rollback_os_comandos_seguem_na_versao_anterior(tmp_path):
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:anterior": "A"}, recusada="B"
    )
    (tmp_path / "anterior").mkdir()
    (tmp_path / "anterior" / "docker-compose.prod.yml").write_text("")
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:anterior {tmp_path}/anterior/docker-compose.prod.yml"
    )


def test_atualizar_decide_a_versao_sozinho(tmp_path):
    # atualizar.sh compares the package's image with the refused one: it must see the package's.
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:anterior": "A"}, recusada="B"
    )
    assert avaliar(comum, 'echo "$NA_ANTERIOR"', ambiente) == "1"
    atualizando = {**ambiente, "ATUALIZANDO": "1"}
    assert avaliar(comum, f'{VERSAO_NO_AR}; echo "[$NA_ANTERIOR]"', atualizando) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml\n[]"
    )


def test_anterior_sem_a_copia_do_compose_usa_o_do_pacote(tmp_path):
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:anterior": "A"}, recusada="B"
    )
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:anterior {tmp_path}/release/docker-compose.prod.yml"
    )


@pytest.mark.parametrize(
    ("imagens", "recusada"),
    [
        ({"kaladrius:nova": "B", "kaladrius:anterior": "A"}, None),  # nothing refused
        ({"kaladrius:nova": "C", "kaladrius:anterior": "A"}, "B"),  # a newer package since
        ({"kaladrius:nova": "B"}, "B"),  # a first installation that did not come up
    ],
)
def test_sem_rollback_os_comandos_usam_a_versao_do_pacote(tmp_path, imagens, recusada):
    comum, ambiente = comum_com_imagens(tmp_path, imagens, recusada)
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml"
    )


def test_a_versao_que_subiu_guarda_o_compose_e_o_caddyfile(tmp_path):
    comum = comum_em(tmp_path, pacote=f"VERSAO=0.54.0\nIMAGEM={IMAGEM}\n")
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.54.0")
    (tmp_path / "release" / "Caddyfile").write_text("caddy 0.54.0")
    avaliar(comum, "guardar_compose_anterior")
    # The package replaces release/ with the next version's; the copy stays.
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.55.0")
    assert (tmp_path / "anterior" / "docker-compose.prod.yml").read_text() == "compose 0.54.0"
    assert (tmp_path / "anterior" / "Caddyfile").read_text() == "caddy 0.54.0"
    assert os.readlink(tmp_path / "anterior" / ".env") == "../.env"
    assert avaliar(comum, 'restaurar_compose_de x && echo "$COMPOSE_ARQUIVO"') == (
        f"{tmp_path}/anterior/docker-compose.prod.yml"
    )


def funcao_do_comando(tmp_path, expressao, ambiente):
    """Runs `expressao` with the functions of the `kaladrius` command defined."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACOTE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(comum_em(tmp_path), bin_ / "comum.sh")
    return subprocess.run(  # noqa: S603 (the package's own command)
        # $0 is the command's path, as when it runs: it finds comum.sh beside itself.
        [BASH, "-c", f'source "$0" versao >/dev/null; {expressao}', str(bin_ / "kaladrius")],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=30,
    )


IP_SEM_ROTA = """#!/bin/sh
# A clinic's network with no way out: no default route.
case "$*" in
  "-4 route get 1.1.1.1") echo "RTNETLINK answers: Network is unreachable" >&2; exit 2 ;;
  "-4 -o addr show scope global")
    echo "2: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0"
    echo "3: enp1s0    inet 192.168.0.10/24 brd 192.168.0.255 scope global enp1s0" ;;
esac
"""


def test_endereco_local_numa_rede_sem_saida(tmp_path):
    (tmp_path / "path").mkdir()
    ip = tmp_path / "path" / "ip"
    ip.write_text(IP_SEM_ROTA)
    ip.chmod(0o755)
    resultado = funcao_do_comando(
        tmp_path, "endereco_local", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "192.168.0.10"


def test_endereco_local_sem_endereco_nenhum_nao_falha(tmp_path):
    (tmp_path / "path").mkdir()
    ip = tmp_path / "path" / "ip"
    ip.write_text("#!/bin/sh\nexit 2\n")
    ip.chmod(0o755)
    resultado = funcao_do_comando(
        tmp_path, "endereco_local; echo fim", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "fim\n"


REGISTRO_DE_CHAMADAS = """#!/bin/sh
echo "$(basename "$0") $*" >> "$CHAMADAS"
"""


@pytest.mark.parametrize(
    ("argumento", "remove"),
    [
        ("remove", True),  # apt
        ("0", True),  # rpm: the last copy goes
        ("0.54.0-1", True),  # pacman runs pre_remove (with the version) only on a removal
        ("upgrade", False),  # apt: an update
        ("1", False),  # rpm: an update (one copy stays)
        ("failed-upgrade", False),
    ],
)
def test_remover_para_o_sistema_so_numa_remocao(tmp_path, argumento, remove):
    for comando in ("systemctl", "docker"):
        falso = tmp_path / comando
        falso.write_text(REGISTRO_DE_CHAMADAS)
        falso.chmod(0o755)
    chamadas = tmp_path / "chamadas"
    chamadas.write_text("")
    resultado = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(PACOTE / "antes_de_remover.sh"), argumento],
        capture_output=True,
        text=True,
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "CHAMADAS": str(chamadas)},
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    desligou = "disable --now kaladrius-backup.timer" in chamadas.read_text()
    assert desligou is remove, chamadas.read_text()


def test_cada_formato_tem_as_dependencias_de_docker():
    # Each package format names Docker and Docker Compose in its own distributions' words.
    for formato in ("deb", "rpm", "archlinux"):
        bloco = re.search(rf"^  {formato}:\n((?:    .*\n)+)", NFPM, re.M).group(1)
        dependencias = bloco.split("depends:")[1].split("recommends:")[0]
        assert "docker" in dependencias and "compose" in dependencias, formato
