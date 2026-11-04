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

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "deploy" / "package"
SERVIDOR = RAIZ / "deploy" / "server"
NFPM = (PACOTE / "nfpm.yaml").read_text()

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")


def conteudo():
    """The (src, dst) pairs of the package's contents."""
    return re.findall(r"- src: (\S+)\n\s+dst: (\S+)", NFPM)


def test_todo_arquivo_do_pacote_existe():
    for origem, _destino in conteudo():
        if (
            origem.startswith("/") or origem == "dist/linux-package"
        ):  # a symlink; written by build.sh
            continue
        assert (RAIZ / origem).is_file(), origem
    for script in re.findall(r"(?:postinstall|postupgrade|preremove|postremove): (\S+)", NFPM):
        assert (RAIZ / script).is_file(), script


def test_cada_tarefa_agendada_roda_um_script_do_pacote():
    destinos = {destino for _origem, destino in conteudo()}
    unidades = [d for d in destinos if d.startswith("/usr/lib/systemd/system/")]
    assert {Path(u).name for u in unidades} == {
        f"kaladrius-{name}.{kind}"
        for name in ("backup", "health", "restore-test")
        for kind in ("service", "timer")
    }
    for unidade in unidades:
        if unidade.endswith(".service"):
            texto = (SERVIDOR / Path(unidade).name).read_text()
            executavel = re.search(r"^ExecStart=(\S+)", texto, re.M).group(1)
            assert executavel in destinos, (unidade, executavel)


def test_o_pacote_liga_as_tarefas_que_traz():
    comum = (SERVIDOR / "common.sh").read_text()
    bloco = comum.split("if installed_by_package; then  # its units came with the package")[1]
    ligadas = set(re.findall(r"kaladrius-[a-z-]+\.timer", bloco.split("return 0")[0]))
    trazidas = {Path(d).name for _o, d in conteudo() if d.endswith(".timer")}
    assert ligadas == trazidas
    # Also when the package is installed again over a configured installation, before the
    # system is started: a removal disabled them, and the new version may not come up.
    instalar = (PACOTE / "post_install.sh").read_text().split('if [ -f "$DIR/.env" ]')[1]
    antes_de_subir = instalar.split('"$DIR/bin/update.sh"')[0]
    assert set(re.findall(r"kaladrius-[a-z-]+\.timer", antes_de_subir)) == trazidas


def comum_em(pasta, pacote=None, env=""):
    """common.sh with its DIR in a temporary folder."""
    (pasta / "release").mkdir(parents=True, exist_ok=True)
    texto = (SERVIDOR / "common.sh").read_text().replace("DIR=/opt/kaladrius", f"DIR={pasta}", 1)
    (pasta / "common.sh").write_text(texto)
    if pacote is not None:
        (pasta / "release" / "linux-package").write_text(pacote)
    (pasta / ".env").write_text(env)
    return pasta / "common.sh"


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
    comum = comum_em(tmp_path, pacote=f"VERSION=0.54.0\nIMAGE={IMAGEM}\n")
    assert avaliar(comum, 'echo "$APP_IMAGE|$DOCS_IMAGE|$PACKAGE_VERSION|$REGISTRY"') == (
        f"{IMAGEM}||0.54.0|ghcr.io"
    )
    assert avaliar(comum, 'echo "$PREVIOUS_APP_IMAGE"') == (
        "ghcr.io/facchini-miguel/kaladrius:previous"
    )
    # No registry login: the image is public.
    assert avaliar(comum, "registry_login && echo sem-login") == "sem-login"


def test_modo_pacote_aceita_outra_imagem(tmp_path):
    comum = comum_em(
        tmp_path, pacote=f"VERSION=0.54.0\nIMAGE={IMAGEM}\n", env="KALADRIUS_IMAGE=k:teste\n"
    )
    assert avaliar(comum, 'echo "$APP_IMAGE $PREVIOUS_APP_IMAGE"') == "k:teste k:previous"
    assert avaliar(comum, 'echo "$APP_IMAGE"', {"KALADRIUS_IMAGE": "outra:1"}) == "outra:1"


def test_sem_pacote_segue_o_google_cloud(tmp_path):
    comum = comum_em(tmp_path)
    # Google Cloud copies the whole deploy/ folder of the image to release/, the package's
    # sources included: they must not switch on the package mode.
    shutil.copytree(PACOTE, tmp_path / "release" / "package")
    app, docs, anterior = avaliar(
        comum, 'echo "$APP_IMAGE $DOCS_IMAGE $PREVIOUS_APP_IMAGE"'
    ).split()
    assert app.endswith("/kaladrius/app:latest") and docs.endswith("/kaladrius/docs:latest")
    assert anterior.endswith("/kaladrius/app:previous")


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
    assert avaliar(comum_em(tmp_path), f'repository_of "{referencia}"') == repositorio


@pytest.mark.parametrize(
    ("acesso", "esperado"),
    [("internal-network", "sim"), ("rede-interna", "sim"), ("internet", "nao")],
)
def test_rede_interna(tmp_path, acesso, esperado):
    comum = comum_em(tmp_path, env=f"KALADRIUS_ACCESS={acesso}\n")
    assert avaliar(comum, "internal_network && echo sim || echo nao") == esperado


def kaladrius(tmp_path, *args, idioma="C"):
    """The `kaladrius` command as installed: beside common.sh, here with DIR in tmp_path."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACOTE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(comum_em(tmp_path), bin_ / "common.sh")
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
    resultado = kaladrius(tmp_path, "help", idioma=idioma)
    assert resultado.returncode == 0, resultado.stderr
    assert trecho in resultado.stdout
    assert "sudo kaladrius configure" in resultado.stdout


@pytest.mark.parametrize("comando", ["ajuda", "ayuda", "--help"])
def test_ajuda_em_outros_nomes(tmp_path, comando):
    assert kaladrius(tmp_path, comando).returncode == 0


def test_comando_desconhecido_falha(tmp_path):
    assert kaladrius(tmp_path, "nao-existe").returncode == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="running as root")
def test_configurar_exige_root(tmp_path):
    resultado = kaladrius(tmp_path, "configure", "--access", "internal-network")
    assert resultado.returncode == 1
    assert "sudo kaladrius configure" in resultado.stderr


def test_nenhum_script_confere_duas_condicoes_numa_linha_so():
    # `[ a ] && [ b ]` alone on a line does not stop a `set -e` script when `a` fails: the
    # restore test passed with no clinic restored until decision 140.
    padrao = re.compile(r"^\s*\[[^]]*\]\s*&&\s*\[[^]]*\]\s*$")
    for script in [*SERVIDOR.glob("*.sh"), *PACOTE.glob("*.sh"), PACOTE / "kaladrius"]:
        for number, linha in enumerate(script.read_text().splitlines(), 1):
            assert not padrao.match(linha), f"{script.name}:{number}: {linha.strip()}"


def test_nenhum_script_usa_grep_q_depois_de_um_cano():
    # With pipefail, `cmd | grep -q x` fails when grep exits at the first match and `cmd` dies
    # writing the rest (SIGPIPE): Kaladrius's own Caddy was taken for another program on 80/443.
    padrao = re.compile(r"\|\s*grep\s+-[a-zA-Z]*q")
    for script in [*SERVIDOR.glob("*.sh"), *PACOTE.glob("*.sh"), PACOTE / "kaladrius"]:
        for number, linha in enumerate(script.read_text().splitlines(), 1):
            assert not padrao.search(linha), f"{script.name}:{number}: {linha.strip()}"


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
        tmp_path, f'is_ipv4 "{endereco}" && echo sim || echo nao', {"PATH": "/usr/bin:/bin"}
    )
    assert resultado.stdout.strip() == ("sim" if valido else "nao"), resultado.stderr


def test_configurar_de_novo_grava_o_novo_usuario_do_administrador(tmp_path):
    # A first run that did not finish wrote .env; the user name typed on the next run is the
    # one created, so .env (read by `kaladrius senha`) must say the same.
    expressao = (
        'rm "$DIR/.env"; write_env internal-network 192.168.0.10 admin a@x.test; '
        'write_env internal-network 192.168.0.11 suporte ""; '
        'grep -c DJANGO_SECRET_KEY "$DIR/.env"; env_value DJANGO_ADMIN_USERNAME; '
        "env_value DJANGO_ADMIN_EMAIL; env_value SITE_HOSTNAME"
    )
    resultado = funcao_do_comando(tmp_path, expressao, {"PATH": "/usr/bin:/bin"})
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.splitlines() == ["1", "suporte", "", "192.168.0.11"]


def test_pasta_dos_backups(tmp_path):
    assert avaliar(comum_em(tmp_path / "a"), "backup_dir") == "/var/backups/kaladrius"
    outra = comum_em(tmp_path / "b", env="KALADRIUS_BACKUP_DIR=/srv/copias\n")
    assert avaliar(outra, "backup_dir") == "/srv/copias"
    # A .env of 0.54 or earlier, not migrated yet (decision 147).
    antiga = comum_em(tmp_path / "c", env="KALADRIUS_BACKUP_PASTA=/srv/antigas\n")
    assert avaliar(antiga, "backup_dir") == "/srv/antigas"


def test_caddy_nunca_recebe_o_endereco_da_documentacao_vazio():
    # An empty address makes the Caddyfile's docs block invalid and Caddy does not start.
    compose = (RAIZ / "deploy" / "docker-compose.prod.yml").read_text()
    assert "DOCS_HOSTNAME: ${DOCS_HOSTNAME:-docs.localhost}" in compose


def test_remover_o_pacote_nunca_apaga_os_dados():
    # The database, the backups and the .env stay; the help printed after a removal shows the
    # commands, for a person to decide (indented lines of the message).
    for script in ("pre_remove.sh", "post_remove.sh"):
        for linha in (PACOTE / script).read_text().splitlines():
            if linha.lstrip().startswith(("#", "printf")) or linha.startswith("    sudo "):
                continue
            assert "volume rm" not in linha and "down -v" not in linha, linha
            if re.search(r"\brm\b", linha):
                # The package repository's apt source (on a purge) is configuration, not data.
                assert linha.strip() in {
                    "rm -f /opt/kaladrius/release/.env",
                    'rm -f "$ETC/apt/sources.list.d/kaladrius.sources"',
                }, linha


def test_o_site_e_conferido_pelo_proprio_servidor(tmp_path):
    # A clinic's router often has no "hairpin NAT": from inside, the clinic's public address
    # never answers, and a good new version would be refused.
    pacote = f"VERSION=0.54.0\nIMAGE={IMAGEM}\n"
    expressao = 'site_curl_options k.example; echo "${CURL_OPTIONS[*]}"'
    internet = comum_em(tmp_path / "a", pacote=pacote, env="KALADRIUS_ACCESS=internet\n")
    assert avaliar(internet, expressao) == "--resolve k.example:443:127.0.0.1"
    interna = comum_em(tmp_path / "b", pacote=pacote, env="KALADRIUS_ACCESS=internal-network\n")
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
    """common.sh in package mode, with a fake `docker` that knows only `imagens` (name: id)."""
    comum = comum_em(tmp_path, pacote="VERSION=0.55.0\nIMAGE=kaladrius:nova\n")
    (tmp_path / "imagens").mkdir()
    for name, ident in imagens.items():
        (tmp_path / "imagens" / name.replace(":", "_")).write_text(ident)
    (tmp_path / "path").mkdir()
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER_FALSO)
    docker.chmod(0o755)
    if recusada is not None:
        (tmp_path / "refused-image").write_text(recusada + "\n")
    ambiente = {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin", "IMAGENS": str(tmp_path / "imagens")}
    return comum, ambiente


# Decided by common.sh itself, for every script that sources it.
VERSAO_NO_AR = 'echo "$APP_IMAGE $COMPOSE_PATH"'


def test_depois_de_um_rollback_os_comandos_seguem_na_versao_anterior(tmp_path):
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, recusada="B"
    )
    (tmp_path / "previous").mkdir()
    (tmp_path / "previous" / "docker-compose.prod.yml").write_text("")
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:previous {tmp_path}/previous/docker-compose.prod.yml"
    )


def test_atualizar_decide_a_versao_sozinho(tmp_path):
    # update.sh compares the package's image with the refused one: it must see the package's.
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, recusada="B"
    )
    assert avaliar(comum, 'echo "$ON_PREVIOUS"', ambiente) == "1"
    atualizando = {**ambiente, "UPDATING": "1"}
    assert avaliar(comum, f'{VERSAO_NO_AR}; echo "[$ON_PREVIOUS]"', atualizando) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml\n[]"
    )


def test_anterior_sem_a_copia_do_compose_usa_o_do_pacote(tmp_path):
    comum, ambiente = comum_com_imagens(
        tmp_path, {"kaladrius:nova": "B", "kaladrius:previous": "A"}, recusada="B"
    )
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:previous {tmp_path}/release/docker-compose.prod.yml"
    )


@pytest.mark.parametrize(
    ("imagens", "recusada"),
    [
        ({"kaladrius:nova": "B", "kaladrius:previous": "A"}, None),  # nothing refused
        ({"kaladrius:nova": "C", "kaladrius:previous": "A"}, "B"),  # a newer package since
        ({"kaladrius:nova": "B"}, "B"),  # a first installation that did not come up
    ],
)
def test_sem_rollback_os_comandos_usam_a_versao_do_pacote(tmp_path, imagens, recusada):
    comum, ambiente = comum_com_imagens(tmp_path, imagens, recusada)
    assert avaliar(comum, VERSAO_NO_AR, ambiente) == (
        f"kaladrius:nova {tmp_path}/release/docker-compose.prod.yml"
    )


def test_a_versao_que_subiu_guarda_o_compose_e_o_caddyfile(tmp_path):
    comum = comum_em(tmp_path, pacote=f"VERSION=0.54.0\nIMAGE={IMAGEM}\n")
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.54.0")
    (tmp_path / "release" / "Caddyfile").write_text("caddy 0.54.0")
    avaliar(comum, "save_previous_compose")
    # The package replaces release/ with the next version's; the copy stays.
    (tmp_path / "release" / "docker-compose.prod.yml").write_text("compose 0.55.0")
    assert (tmp_path / "previous" / "docker-compose.prod.yml").read_text() == "compose 0.54.0"
    assert (tmp_path / "previous" / "Caddyfile").read_text() == "caddy 0.54.0"
    assert os.readlink(tmp_path / "previous" / ".env") == "../.env"
    assert avaliar(comum, 'restore_compose_from x && echo "$COMPOSE_PATH"') == (
        f"{tmp_path}/previous/docker-compose.prod.yml"
    )


def funcao_do_comando(tmp_path, expressao, ambiente):
    """Runs `expressao` with the functions of the `kaladrius` command defined."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    shutil.copy(PACOTE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(comum_em(tmp_path), bin_ / "common.sh")
    return subprocess.run(  # noqa: S603 (the package's own command)
        # $0 is the command's path, as when it runs: it finds common.sh beside itself.
        [BASH, "-c", f'source "$0" version >/dev/null; {expressao}', str(bin_ / "kaladrius")],
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
        tmp_path, "local_address", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "192.168.0.10"


def test_endereco_local_sem_endereco_nenhum_nao_falha(tmp_path):
    (tmp_path / "path").mkdir()
    ip = tmp_path / "path" / "ip"
    ip.write_text("#!/bin/sh\nexit 2\n")
    ip.chmod(0o755)
    resultado = funcao_do_comando(
        tmp_path, "local_address; echo fim", {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "fim\n"


REGISTRO_DE_CHAMADAS = """#!/bin/sh
echo "$(basename "$0") $*" >> "$CHAMADAS"
"""


def falsos(pasta, *comandos):
    """Fake `comandos` in `pasta` that only record their calls; returns the calls file and an
    environment with them first in PATH."""
    pasta.mkdir(exist_ok=True)
    for comando in comandos:
        falso = pasta / comando
        falso.write_text(REGISTRO_DE_CHAMADAS)
        falso.chmod(0o755)
    chamadas = pasta / "chamadas"
    chamadas.write_text("")
    return chamadas, {"PATH": f"{pasta}:/usr/bin:/bin", "CHAMADAS": str(chamadas)}


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
    chamadas, ambiente = falsos(tmp_path / "path", "systemctl", "docker")
    resultado = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(PACOTE / "pre_remove.sh"), argumento],
        capture_output=True,
        text=True,
        env=ambiente,
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


def test_senha_no_modo_texto_guarda_os_espacos(tmp_path):
    # Without whiptail (openSUSE, Arch Linux) the password is read as typed, spaces included.
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    shutil.copy(PACOTE / "kaladrius", bin_ / "kaladrius")
    shutil.copy(comum_em(tmp_path), bin_ / "common.sh")
    resultado = subprocess.run(  # noqa: S603 (the package's own command)
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
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "  minha senha "


@pytest.mark.parametrize("idioma", ["pt_BR.UTF-8", "es_ES.UTF-8", "C"])
def test_ajuda_explica_as_duas_formas_de_atualizar(tmp_path, idioma):
    # With the package repository (which the package adds), the system's updates; on Arch
    # Linux or without it, the next version's package from the releases.
    saida = kaladrius(tmp_path, "help", idioma=idioma).stdout
    for comando in ("sudo apt upgrade", "sudo dnf upgrade", "sudo zypper update", "pacman -U"):
        assert comando in saida
    assert "github.com/facchini-miguel/kaladrius/releases" in saida


def test_certificado_com_o_caddy_parado_nao_deixa_arquivo(tmp_path):
    destino = tmp_path / "kaladrius-certificate.crt"
    expressao = (
        "require_root() { :; }; compose() { return 1; }; "
        f'echo KALADRIUS_ACCESS=internal-network > "$DIR/.env"; certificate "{destino}"'
    )
    resultado = funcao_do_comando(tmp_path, expressao, {"PATH": "/usr/bin:/bin"})
    assert resultado.returncode == 1
    assert "sudo kaladrius start" in resultado.stderr
    assert not destino.exists()


def depois_de_instalar(tmp_path, argumento, admin_criado, ambiente=None, configurado=True):
    """post_install.sh with DIR and ETC in tmp_path, beside the real common.sh (its DIR there
    too); systemctl, systemd-run, docker and update.sh faked, the systemd units' folder in
    tmp_path."""
    dir_ = tmp_path / "opt"
    (dir_ / "release").mkdir(parents=True, exist_ok=True)
    (dir_ / "bin").mkdir(exist_ok=True)
    shutil.copytree(PACOTE / "repository", dir_ / "repository", dirs_exist_ok=True)
    (dir_ / "release" / "linux-package").write_text(f"VERSION=0.55.0\nIMAGE={IMAGEM}\n")
    texto = (SERVIDOR / "common.sh").read_text().replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
    (dir_ / "bin" / "common.sh").write_text(texto)
    if configurado and not (dir_ / ".env").exists():
        (dir_ / ".env").write_text("SITE_HOSTNAME=192.168.0.10\n")
    if admin_criado:
        (dir_ / "admin-created").write_text("")
    chamadas, ambiente_falso = falsos(tmp_path / "path", "systemctl", "systemd-run", "docker")
    update = dir_ / "bin" / "update.sh"
    update.write_text(REGISTRO_DE_CHAMADAS)
    update.chmod(0o755)
    script = tmp_path / "post_install.sh"
    texto = (PACOTE / "post_install.sh").read_text()
    texto = texto.replace("DIR=/opt/kaladrius", f"DIR={dir_}", 1)
    script.write_text(texto.replace("ETC=/etc", f"ETC={tmp_path / 'etc'}", 1))
    (tmp_path / "systemd").mkdir(exist_ok=True)
    resultado = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(script), argumento],
        capture_output=True,
        text=True,
        env={**ambiente_falso, "SYSTEMD_DIR": str(tmp_path / "systemd"), **(ambiente or {})},
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout, chamadas.read_text()


def test_instalar_de_novo_sem_administrador_volta_as_perguntas(tmp_path):
    # A first `configure` that stopped after writing .env: installing the package again must not
    # bring the system up with no account to log in.
    saida, chamadas = depois_de_instalar(tmp_path, "1", admin_criado=False)
    assert "update.sh" not in chamadas
    assert "sudo kaladrius configure" in saida


def test_atualizar_o_pacote_configurado_sobe_a_versao_nova(tmp_path):
    _saida, chamadas = depois_de_instalar(tmp_path, "2", admin_criado=True)
    assert "update.sh --force" in chamadas
    assert "systemd-run" not in chamadas


def test_no_pacman_a_atualizacao_leva_as_variaveis(tmp_path):
    # pacman: update.sh runs as its own systemd unit, which starts with a clean environment. The
    # names of 0.54 and earlier (decision 147) still work, and go along under the new ones.
    for ambiente in (
        {"KALADRIUS_IMAGE": "kaladrius:teste", "HEALTH_WAIT": "60"},
        {"KALADRIUS_IMAGEM": "kaladrius:teste", "SAUDE_ESPERA": "60"},
    ):
        _saida, chamadas = depois_de_instalar(
            tmp_path, "0.55.0-1", admin_criado=True, ambiente=ambiente
        )
        linha = next(c for c in chamadas.splitlines() if c.startswith("systemd-run"))
        assert "--setenv=KALADRIUS_IMAGE=kaladrius:teste" in linha
        assert "--setenv=HEALTH_WAIT=60" in linha
        assert "--unit=kaladrius-package-update" in linha


@pytest.mark.parametrize(
    ("admin_criado_ha_horas", "falha"),
    [
        (None, False),  # the setup has not finished
        (3, False),  # installed hours ago, before the first daily backup
        (24 * 30, True),  # a month later no backup at all is a failure: a disk not mounted?
    ],
)
def test_teste_de_restauracao_sem_backup(tmp_path, admin_criado_ha_horas, falha):
    comum_em(
        tmp_path,
        pacote=f"VERSION=0.54.0\nIMAGE={IMAGEM}\n",
        env=(
            f"KALADRIUS_BACKUP_DIR={tmp_path / 'nao-existe'}\n"
            "MONITOR_RESTORE_URL=http://monitor.test\n"
        ),
    )
    if admin_criado_ha_horas is not None:
        admin = tmp_path / "admin-created"
        admin.write_text("")
        quando = time.time() - admin_criado_ha_horas * 3600
        os.utime(admin, (quando, quando))
    shutil.copy(SERVIDOR / "test_restore.sh", tmp_path / "test_restore.sh")
    chamadas, ambiente = falsos(tmp_path / "path", "docker", "curl")
    resultado = subprocess.run(  # noqa: S603 (the server's own script)
        [BASH, str(tmp_path / "test_restore.sh")],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=30,
    )
    if falha:
        assert resultado.returncode != 0
        assert "No backup in" in resultado.stderr
        assert "curl -fsS -m 10 --retry 3 -o /dev/null http://monitor.test/fail" in (
            chamadas.read_text()
        )
    else:
        assert resultado.returncode == 0, resultado.stderr
        assert "No backup in" in resultado.stdout and "to test yet" in resultado.stdout
        assert "sudo kaladrius backup" in resultado.stdout
        assert "curl" not in chamadas.read_text()  # the monitor hears no success, no failure


@pytest.mark.parametrize("comando", ["start", "restart"])
def test_iniciar_sem_administrador_manda_terminar_a_configuracao(tmp_path, comando):
    # A setup that stopped before the administrator: starting the system would leave nobody
    # able to log in. `logs` and `stop` still work, to see why.
    expressao = (
        'require_root() { :; }; compose() { echo "compose $*"; }; echo X=1 > "$DIR/.env"; '
        f"require_admin && echo {comando}"
    )
    resultado = funcao_do_comando(tmp_path, expressao, {"PATH": "/usr/bin:/bin"})
    assert resultado.returncode == 1
    assert "sudo kaladrius configure" in resultado.stderr
    (tmp_path / "admin-created").write_text("")
    resultado = funcao_do_comando(tmp_path, expressao, {"PATH": "/usr/bin:/bin"})
    assert resultado.stdout.strip() == comando, resultado.stderr
    kaladrius_ = (PACOTE / "kaladrius").read_text()
    assert re.search(
        rf"^  {comando} \| \w+\) require_root {comando}; require_admin;", kaladrius_, re.M
    )


IMPRESSAO_DIGITAL = "9D3A0438FF6C00F91CA1A0ABA5C335B2EB367ABA"  # decision 142


def impressao_digital(armadura):
    """The fingerprint of an ASCII-armored OpenPGP v4 public key: SHA-1 of its first packet."""
    linhas = armadura.strip().splitlines()
    corpo = linhas[linhas.index("") + 1 : -1]
    dados = base64.b64decode("".join(linha for linha in corpo if not linha.startswith("=")))
    if dados[0] & 0x40:  # new packet format
        size, start = (
            (dados[1], 2) if dados[1] < 192 else (((dados[1] - 192) << 8) + dados[2] + 192, 3)
        )
    else:  # old format: the length type in the low two bits
        n = {0: 1, 1: 2, 2: 4}[dados[0] & 3]
        size, start = int.from_bytes(dados[1 : 1 + n]), 1 + n
    pacote = dados[start : start + size]
    return hashlib.sha1(b"\x99" + len(pacote).to_bytes(2) + pacote).hexdigest().upper()  # noqa: S324


def test_o_repositorio_que_o_pacote_traz_e_o_publicado():
    # The apt source carries the key in Signed-By (deb822: one space before each line, "." for
    # an empty one); both files point to the software's own folder on packages.facchini.eti.br.
    fonte = (PACOTE / "repository" / "kaladrius.sources").read_text()
    assert "URIs: https://packages.facchini.eti.br/kaladrius/deb\n" in fonte
    assert "Suites: stable\nComponents: main\nArchitectures: amd64\n" in fonte
    linhas = fonte.split("Signed-By:\n", 1)[1].splitlines()
    chave = "\n".join("" if linha == " ." else linha.removeprefix(" ") for linha in linhas)
    assert impressao_digital(chave) == IMPRESSAO_DIGITAL
    repo = (PACOTE / "repository" / "kaladrius.repo").read_text()
    for linha in (
        "baseurl=https://packages.facchini.eti.br/kaladrius/rpm",
        "gpgcheck=1",
        "repo_gpgcheck=1",
        "autorefresh=1",
        "gpgkey=https://packages.facchini.eti.br/facchini.asc",
    ):
        assert linha in repo.splitlines()


@pytest.mark.parametrize(
    ("argumento", "pastas", "esperado"),
    [
        ("configure", ["apt/sources.list.d"], "apt/sources.list.d/kaladrius.sources"),
        ("1", ["yum.repos.d"], "yum.repos.d/kaladrius.repo"),  # dnf
        ("2", ["yum.repos.d"], "yum.repos.d/kaladrius.repo"),  # an update from a downloaded rpm
        ("1", ["zypp/repos.d"], "zypp/repos.d/kaladrius.repo"),  # zypper
        ("0.55.0-1", ["apt/sources.list.d", "yum.repos.d"], None),  # Arch Linux: none
    ],
)
def test_o_pacote_adiciona_o_repositorio(tmp_path, argumento, pastas, esperado):
    for pasta in pastas:
        (tmp_path / "etc" / pasta).mkdir(parents=True)
    saida, _chamadas = depois_de_instalar(tmp_path, argumento, admin_criado=True)
    adicionados = sorted(
        str(a.relative_to(tmp_path / "etc")) for a in (tmp_path / "etc").rglob("kaladrius.*")
    )
    assert adicionados == ([esperado] if esperado else [])
    if esperado:
        origem = PACOTE / "repository" / Path(esperado).name
        assert (tmp_path / "etc" / esperado).read_text() == origem.read_text()
        assert "package repository added" in saida


def test_o_repositorio_ja_configurado_nao_e_adicionado_de_novo(tmp_path):
    # By hand under another name, or the file of an earlier installation, as the person left it.
    fontes = tmp_path / "etc" / "apt" / "sources.list.d"
    fontes.mkdir(parents=True)
    (fontes / "facchini.list").write_text(
        "deb [signed-by=/etc/apt/keyrings/facchini.asc]"
        " https://packages.facchini.eti.br/kaladrius/deb stable main\n"
    )
    depois_de_instalar(tmp_path, "configure", admin_criado=True)
    assert sorted(a.name for a in fontes.iterdir()) == ["facchini.list"]
    (fontes / "facchini.list").unlink()
    # Its own file, changed by hand (another address, say): left as it is.
    (fontes / "kaladrius.sources").write_text("Enabled: no\nURIs: http://espelho.exemplo/k\n")
    saida, _chamadas = depois_de_instalar(tmp_path, "configure", admin_criado=True)
    assert (fontes / "kaladrius.sources").read_text().startswith("Enabled: no")
    assert "package repository added" not in saida


def test_sem_repositorio_por_escolha_tambem_nas_proximas_instalacoes(tmp_path):
    fontes = tmp_path / "etc" / "apt" / "sources.list.d"
    fontes.mkdir(parents=True)
    depois_de_instalar(
        tmp_path, "configure", admin_criado=True, ambiente={"KALADRIUS_NO_REPOSITORY": "1"}
    )
    assert not list(fontes.iterdir())
    depois_de_instalar(tmp_path, "configure", admin_criado=True)  # a later update: still none
    assert not list(fontes.iterdir())


def test_a_primeira_instalacao_ja_adiciona_o_repositorio(tmp_path):
    # Before `configure`: the server is on the repository even if the setup never finishes.
    fontes = tmp_path / "etc" / "apt" / "sources.list.d"
    fontes.mkdir(parents=True)
    saida, _chamadas = depois_de_instalar(
        tmp_path, "configure", admin_criado=False, configurado=False
    )
    assert (fontes / "kaladrius.sources").exists()
    assert "sudo kaladrius configure" in saida


@pytest.mark.parametrize(("argumento", "fica"), [("remove", True), ("purge", False)])
def test_remover_mantem_o_repositorio_e_purge_apaga(tmp_path, argumento, fica):
    fontes = tmp_path / "etc" / "apt" / "sources.list.d"
    fontes.mkdir(parents=True)
    (fontes / "kaladrius.sources").write_text("Types: deb\n")
    script = tmp_path / "post_remove.sh"
    texto = (
        (PACOTE / "post_remove.sh").read_text().replace("ETC=/etc", f"ETC={tmp_path / 'etc'}", 1)
    )
    script.write_text(texto.replace("rm -f /opt/kaladrius/", f"rm -f {tmp_path}/", 1))
    _chamadas, ambiente = falsos(tmp_path / "path", "systemctl")
    resultado = subprocess.run(  # noqa: S603 (the package's own script)
        [shutil.which("sh"), str(script), argumento],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert ("sudo rm " + str(fontes / "kaladrius.sources") in resultado.stdout) is fica


DOCKER_COMANDOS = """#!/bin/bash
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
    ("conhecidos", "esperado"),
    [
        ("record_backup", "record_backup a.dump 10"),
        # The previous version, after a rollback: only the name before decision 148.
        ("registrar_backup", "registrar_backup a.dump 10"),
    ],
)
def test_manage_usa_o_nome_antigo_so_num_app_que_nao_o_conhece(tmp_path, conhecidos, esperado):
    comum = comum_em(tmp_path)
    (tmp_path / "path").mkdir()
    docker = tmp_path / "path" / "docker"
    docker.write_text(DOCKER_COMANDOS)
    docker.chmod(0o755)
    chamadas = tmp_path / "chamadas"
    ambiente = {
        "PATH": f"{tmp_path / 'path'}:/usr/bin:/bin",
        "KNOWN": conhecidos,
        "CALLS": str(chamadas),
    }
    avaliar(comum, "manage record_backup a.dump 10 -- registrar_backup a.dump 10", ambiente)
    avaliar(comum, "manage health", ambiente)  # no old name given: always the new one
    assert chamadas.read_text().splitlines() == [esperado, "health"]


CURL_SO_O_ANTIGO = """#!/bin/sh
# Only the health page's address before decision 155 answers (an app rolled back to 0.55).
case "$*" in *"/api/v1/saude"*) exit 0 ;; *) exit 22 ;; esac
"""


@pytest.mark.parametrize(
    ("curl", "responde"), [(CURL_SO_O_ANTIGO, "sim"), ("#!/bin/sh\nexit 22\n", "nao")]
)
def test_a_saude_pelo_endereco_novo_ou_pelo_antigo(tmp_path, curl, responde):
    comum = comum_em(tmp_path)
    (tmp_path / "path").mkdir()
    falso = tmp_path / "path" / "curl"
    falso.write_text(curl)
    falso.chmod(0o755)
    ambiente = {"PATH": f"{tmp_path / 'path'}:/usr/bin:/bin"}
    expressao = "CURL_OPTIONS=(); health_answers k.example && echo sim || echo nao"
    assert avaliar(comum, expressao, ambiente) == responde
