"""Report of the migrations a pull request adds (decision 139)."""

import subprocess

import pytest
from django.db import connection, migrations, models
from django.db.migrations.loader import MigrationLoader

from apps.core.management.commands import relatorio_migracoes as relatorio

CONVENIOS = ("convenios", "0003_seguros_de_cada_pais")


def _antes(app, nome):
    return MigrationLoader(connection).project_state((app, nome), at_end=False)


def _tipos(alertas):
    return [alerta.tipo for alerta in alertas]


@pytest.mark.django_db
def test_operacoes_que_apagam_ou_quebram_a_volta():
    antes = _antes(*CONVENIOS)
    remover = migrations.RemoveField("carteirinha", "titular")
    assert _tipos(relatorio.alertas_da_operacao(remover, "convenios", antes)) == [
        relatorio.APAGA,
        relatorio.QUEBRA_VOLTA,
    ]
    tabela = migrations.DeleteModel("Carteirinha")
    assert _tipos(relatorio.alertas_da_operacao(tabela, "convenios", antes)) == [relatorio.APAGA]
    renomear = migrations.RenameField("convenio", "nome", "nome_novo")
    assert relatorio.QUEBRA_VOLTA in _tipos(
        relatorio.alertas_da_operacao(renomear, "convenios", antes)
    )


@pytest.mark.django_db
def test_operacoes_sem_volta_e_campos_alterados():
    antes = _antes(*CONVENIOS)
    sem_volta = migrations.RunPython(lambda apps, schema: None)
    assert _tipos(relatorio.alertas_da_operacao(sem_volta, "convenios", antes)) == [
        relatorio.SEM_VOLTA
    ]
    com_volta = migrations.RunPython(lambda a, s: None, migrations.RunPython.noop)
    assert relatorio.alertas_da_operacao(com_volta, "convenios", antes) == []
    # convenio.nome is varchar(200): shorter, another type, or required, deserve a look.
    menor = migrations.AlterField("convenio", "nome", models.CharField(max_length=50))
    assert _tipos(relatorio.alertas_da_operacao(menor, "convenios", antes)) == [relatorio.REVISAR]
    maior = migrations.AlterField("convenio", "nome", models.CharField(max_length=300))
    assert relatorio.alertas_da_operacao(maior, "convenios", antes) == []
    numero = migrations.AlterField("convenio", "nome", models.IntegerField())
    assert _tipos(relatorio.alertas_da_operacao(numero, "convenios", antes)) == [relatorio.REVISAR]


@pytest.mark.django_db
def test_relatorio_de_uma_migracao_real():
    """convenios.0003 renamed registro_ans: the previous version would not work with it."""
    (migracao,) = relatorio.analisar([CONVENIOS])
    assert 'RENAME COLUMN "registro_ans" TO "registro"' in migracao.sql
    assert _tipos(migracao.alertas) == [relatorio.QUEBRA_VOLTA]  # varchar 6 -> 20 is fine
    texto = relatorio.markdown([migracao], falhas=[])
    assert "### ⚠️ Needs attention" in texto and "convenios.0003_seguros_de_cada_pais" in texto
    assert "Back and forth tested" in texto and "```sql" in texto


def test_relatorio_sem_migracoes():
    assert "No new migration" in relatorio.markdown([])


def test_migracoes_novas_le_o_git(monkeypatch):
    saida = (
        "apps/convenios/migrations/0004_x.py\napps/core/forms.py\napps/core/migrations/0019_y.py\n"
    )

    def git(*args, **kwargs):
        assert args[0][1:4] == ["diff", "--name-only", "--diff-filter=A"]
        return subprocess.CompletedProcess(args[0], 0, stdout=saida, stderr="")

    monkeypatch.setattr(relatorio.subprocess, "run", git)
    assert relatorio.migracoes_novas("origin/main") == [
        ("convenios", "0004_x"),
        ("core", "0019_y"),
    ]


@pytest.mark.django_db(transaction=True)
def test_ida_e_volta_de_uma_migracao_real():
    assert relatorio.testar_volta([CONVENIOS]) == []
