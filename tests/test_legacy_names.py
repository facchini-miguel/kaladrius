"""The move to the names of decision 147 on a server installed with 0.54 or earlier: the
migration of its state files, .env and scheduled tasks (deploy/server/common.sh), the package
updated from 0.54, and the old names that still work. The Google Cloud bridge that ran the first
update there was removed by decision 152, once production had moved."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
COMMON = RAIZ / "deploy" / "server" / "common.sh"
# Run as root, these commands would reach the real Docker: they are compared only when refused.
COMO_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="running as root")


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
        "DJANGO_PROXY_REVERSO=1\n"
    )
    dir_ = comum(tmp_path, env)
    sistema = tmp_path / "systemd"
    sistema.mkdir()
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert (dir_ / ".env").read_text() == (
        "# a comment\nDJANGO_SECRET_KEY=x=y\nKALADRIUS_ACCESS=internal-network\n"
        "KALADRIUS_BACKUP_DIR=/srv/b\nSITE_HOSTNAME=192.168.0.10\nAPP_IMAGE=k:1\n"
        # The app's variable (decision 149): the new name added, the old one kept for the
        # previous version's app after a rollback.
        "DJANGO_PROXY_REVERSO=1\nDJANGO_REVERSE_PROXY=1\n"
    )
    assert (dir_ / ".env.before-147").read_text() == env
    # Again: nothing changes, and the copy of the original stays.
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert (dir_ / ".env.before-147").read_text() == env


def test_migrar_os_arquivos_de_estado(tmp_path):
    dir_ = comum(tmp_path, "")
    for name in ("admin-criado", "sem-repositorio", "imagem-recusada"):
        (dir_ / name).write_text(name)
    (dir_ / "demonstracao").mkdir()
    (dir_ / "demonstracao" / "base-date").write_text("2026-10-30")
    (dir_ / "anterior").mkdir()
    (dir_ / "saude").mkdir()
    (dir_ / "saude" / "amostras.jsonl").write_text('{"momento": "2026-11-03T10:00:00Z"}\n')
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
    # The health samples (decision 149): the app reads the old lines too.
    assert (dir_ / "health" / "samples.jsonl").read_text().startswith('{"momento"')
    assert not (dir_ / "saude").exists()


def test_o_servidor_do_google_cloud_guarda_os_scripts_antigos(tmp_path):
    # The pointer bin/atualizar.sh, kept by 0.55 for the VM's old startup script, goes with the
    # scripts of 0.54 to legacy/bin; the old update lock, which no script takes, goes away.
    dir_ = comum(tmp_path, "")
    (dir_ / "bin").mkdir()
    for name in ("atualizar.sh", "comum.sh", "saude.sh", "update.sh"):
        (dir_ / "bin" / name).write_text(name)
    (dir_ / "atualizar.lock").write_text("")
    sistema = tmp_path / "systemd"
    sistema.mkdir()
    avaliar(dir_, "migrate_legacy_names", {"SYSTEMD_DIR": str(sistema)})
    assert sorted(p.name for p in (dir_ / "bin").iterdir()) == ["update.sh"]
    assert sorted(p.name for p in (dir_ / "legacy" / "bin").iterdir()) == [
        "atualizar.sh",
        "comum.sh",
        "saude.sh",
    ]
    assert not (dir_ / "atualizar.lock").exists()


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


def test_a_configuracao_le_o_nome_antigo_da_variavel(monkeypatch):
    # The app's variables of decision 149: the new name wins, the old one is read without it.
    from config.settings import env_renomeada

    for name in ("DJANGO_REVERSE_PROXY", "DJANGO_PROXY_REVERSO"):
        monkeypatch.delenv(name, raising=False)
    assert env_renomeada("DJANGO_REVERSE_PROXY", "DJANGO_PROXY_REVERSO") is False
    assert env_renomeada("DJANGO_REVERSE_PROXY", "DJANGO_PROXY_REVERSO", padrao=True) is True
    monkeypatch.setenv("DJANGO_PROXY_REVERSO", "1")
    assert env_renomeada("DJANGO_REVERSE_PROXY", "DJANGO_PROXY_REVERSO") is True
    monkeypatch.setenv("DJANGO_REVERSE_PROXY", "0")
    assert env_renomeada("DJANGO_REVERSE_PROXY", "DJANGO_PROXY_REVERSO") is False
