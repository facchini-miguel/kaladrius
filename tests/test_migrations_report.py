"""Report of the migrations a pull request adds (decision 139)."""

import subprocess
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError
from django.db import connection, migrations, models
from django.db.migrations.loader import MigrationLoader

from apps.core.management.commands import migrations_report as relatorio

HEALTH_PLANS = ("convenios", "0003_seguros_de_cada_pais")


def _antes(app, nome):
    return MigrationLoader(connection).project_state((app, nome), at_end=False)


def _tipos(alerts):
    return [health_alert.kind for health_alert in alerts]


def _alertas(operacao):
    return _tipos(relatorio.operation_alerts(operacao, "convenios", _antes(*HEALTH_PLANS)))


@pytest.mark.django_db
def test_operacoes_que_apagam_ou_quebram_a_volta():
    remover = migrations.RemoveField("carteirinha", "titular")
    assert _alertas(remover) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    # The previous version still queries the dropped table: every page using it would fail.
    table = migrations.DeleteModel("Carteirinha")
    assert _alertas(table) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    renomear = migrations.RenameField("convenio", "nome", "nome_novo")
    assert relatorio.BREAKS_ROLLBACK in _alertas(renomear)


@pytest.mark.django_db
def test_renomear_mantendo_tabela_e_coluna_nao_alerta():
    """Decision 156: renamed in the code only, the table and column kept, nothing reaches the
    database; the previous version still works."""
    before = _antes(*HEALTH_PLANS)
    fixar = migrations.AlterModelTable("convenio", "convenios_convenio")
    assert relatorio.operation_alerts(fixar, "convenios", before) == []
    before = relatorio._after(fixar, "convenios", before)
    modelo = migrations.RenameModel("Convenio", "HealthPlan")
    assert relatorio.operation_alerts(modelo, "convenios", before) == []
    # The table follows the model's name when it is not pinned: the previous version breaks.
    solto = migrations.RenameModel("Carteirinha", "Card")
    assert _tipos(relatorio.operation_alerts(solto, "convenios", before)) == [
        relatorio.BREAKS_ROLLBACK
    ]
    before = relatorio._after(modelo, "convenios", before)
    column = migrations.AlterField(
        "healthplan", "nome", models.CharField(max_length=100, db_column="nome")
    )
    before = relatorio._after(column, "convenios", before)
    field = migrations.RenameField("healthplan", "nome", "name")
    assert relatorio.operation_alerts(field, "convenios", before) == []


@pytest.mark.django_db
def test_operacoes_sem_volta_e_campos_alterados():
    sem_volta = migrations.RunPython(lambda apps, schema: None)
    assert _alertas(sem_volta) == [relatorio.NO_ROLLBACK]
    com_volta = migrations.RunPython(lambda a, s: None, migrations.RunPython.noop)
    assert _alertas(com_volta) == []
    # convenio.nome is varchar(200): shorter or another type deserve a look.
    assert _alertas(migrations.AlterField("convenio", "nome", models.CharField(max_length=50))) == [
        relatorio.REVIEW
    ]
    assert (
        _alertas(migrations.AlterField("convenio", "nome", models.CharField(max_length=300))) == []
    )
    assert _alertas(migrations.AlterField("convenio", "nome", models.IntegerField())) == [
        relatorio.REVIEW
    ]
    # carteirinha.validade may be empty: made required, existing rows and the previous version
    # (which may still save it empty) fail.
    is_required = migrations.AlterField("carteirinha", "validade", models.DateField())
    assert _alertas(is_required) == [relatorio.REVIEW, relatorio.BREAKS_ROLLBACK]


@pytest.mark.django_db
def test_alterar_uma_chave_estrangeira():
    """A ForeignKey changed only in on_delete/related_name: same column, nothing to flag. It used
    to crash: the field of the operation is not attached to a model, its related model is a
    string and it has no db_type."""
    key = migrations.AlterField(
        "carteirinha",
        "convenio",
        models.ForeignKey(
            "convenios.convenio", on_delete=models.CASCADE, related_name="outras_carteirinhas"
        ),
    )
    assert _alertas(key) == []


@pytest.mark.django_db
def test_coluna_obrigatoria_nova():
    """The previous version's inserts leave a new column out: NOT NULL with no database default
    makes them fail (Django's Python default only fills the existing rows)."""
    is_required = migrations.AddField(
        "convenio", "sigla", models.CharField(max_length=5, default="")
    )
    assert _alertas(is_required) == [relatorio.BREAKS_ROLLBACK]
    vazia = migrations.AddField("convenio", "sigla", models.CharField(max_length=5, null=True))
    assert _alertas(vazia) == []
    com_padrao = migrations.AddField(
        "convenio", "sigla", models.CharField(max_length=5, db_default="")
    )
    assert _alertas(com_padrao) == []
    muitos = migrations.AddField("convenio", "outros", models.ManyToManyField("convenios.convenio"))
    assert _alertas(muitos) == []


@pytest.mark.django_db
def test_separate_database_and_state_e_inspecionado():
    """Only the database operations reach the database: a column dropped there is flagged."""
    escondida = migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RemoveField("carteirinha", "titular")],
        state_operations=[],
    )
    assert _alertas(escondida) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    so_estado = migrations.SeparateDatabaseAndState(
        state_operations=[migrations.RemoveField("carteirinha", "titular")]
    )
    assert _alertas(so_estado) == []


@pytest.mark.django_db
def test_relatorio_de_uma_migracao_real():
    """convenios.0003 renamed registro_ans and added two required columns with no database
    default: the previous version would not work with it."""
    (migracao,) = relatorio.analyze([HEALTH_PLANS])
    assert 'RENAME COLUMN "registro_ans" TO "registro"' in migracao.sql
    # varchar 6 -> 20 is fine; the rename and carteirinha.grupo and .beneficiario are not.
    assert _tipos(migracao.alerts) == [relatorio.BREAKS_ROLLBACK] * 3
    texto = relatorio.markdown([migracao], falhas=[])
    assert "### ⚠️ Needs attention" in texto and "convenios.0003_seguros_de_cada_pais" in texto
    assert "Back and forth tested" in texto and "```sql" in texto


def test_relatorio_sem_migracoes():
    assert "No new migration" in relatorio.markdown([])


def test_relatorio_de_migracao_ja_aplicada_alterada():
    texto = relatorio.markdown(
        [], alteradas=[("convenios", "0003_x", "M"), ("core", "0001_y", "D")]
    )
    assert "### ⚠️ Needs attention" in texto
    assert f"**convenios.0003_x** — {relatorio.CHANGED}: edited" in texto
    assert f"**core.0001_y** — {relatorio.CHANGED}: deleted" in texto
    assert "the database does not change" not in texto


def test_comentario_cabe_no_limite_do_github():
    """GitHub refuses a comment over 65,536 characters: the SQL is left out first, then cut."""
    grande = relatorio.MigrationEntry("convenios", "0004_x", sql="SELECT 1;\n" * 10_000)
    grande.operacoes = [("Add field x", [])]
    completo = relatorio.markdown([grande])
    assert len(completo) > relatorio.COMMENT_LIMIT and "```sql" in completo
    curto = relatorio.markdown([grande], limit=relatorio.COMMENT_LIMIT)
    assert len(curto) <= relatorio.COMMENT_LIMIT
    assert "```sql" not in curto and "The SQL is left out" in curto and "Add field x" in curto
    muitas = [
        relatorio.MigrationEntry("a", f"{n:04}_x", operacoes=[("y" * 1000, [])]) for n in range(80)
    ]
    cortado = relatorio.markdown(muitas, limit=relatorio.COMMENT_LIMIT)
    assert len(cortado) <= relatorio.COMMENT_LIMIT and cortado.endswith("summary)\n")


def test_migracoes_do_diff_le_o_git(monkeypatch):
    """Folders become labels (apps/health_plans is "convenios", decision 145), and a migration
    moved with its folder is unchanged when its text is the same, edited when it is not."""
    saida = (
        "A\tapps/health_plans/migrations/0004_x.py\n"
        "M\tapps/core/forms.py\n"
        "A\tapps/core/migrations/0019_y.py\n"
        "M\tapps/health_plans/migrations/0003_seguros_de_cada_pais.py\n"
        "D\tapps/core/migrations/0002_z.py\n"
        "M\tapps/core/migrations/__init__.py\n"
        "D\tapps/agenda/migrations/0001_initial.py\n"
        "A\tapps/schedule/migrations/0001_initial.py\n"
        "D\tapps/agenda/migrations/0003_agendamento.py\n"
        "A\tapps/schedule/migrations/0003_agendamento.py\n"
    )
    textos = {
        "origin/main:apps/agenda/migrations/0001_initial.py": "igual",
        "HEAD:apps/schedule/migrations/0001_initial.py": "igual",
        "origin/main:apps/agenda/migrations/0003_agendamento.py": "import apps.agenda.models",
        "HEAD:apps/schedule/migrations/0003_agendamento.py": "import apps.schedule.models",
    }

    def git(args, **kwargs):
        if args[1] == "show":
            return subprocess.CompletedProcess(args, 0, stdout=textos[args[2]], stderr="")
        assert args[1:4] == ["diff", "--name-status", "--no-renames"]
        return subprocess.CompletedProcess(args, 0, stdout=saida, stderr="")

    monkeypatch.setattr(relatorio.subprocess, "run", git)
    assert relatorio.migrations_from_diff("origin/main") == (
        [("convenios", "0004_x"), ("core", "0019_y")],
        [
            ("agenda", "0003_agendamento", "M"),
            ("convenios", "0003_seguros_de_cada_pais", "M"),
            ("core", "0002_z", "D"),
        ],
    )


def test_migracoes_do_diff_quando_o_git_falha(monkeypatch):
    def git(args, **kwargs):
        return subprocess.CompletedProcess(args, 128, stdout="", stderr="unknown revision")

    monkeypatch.setattr(relatorio.subprocess, "run", git)
    with pytest.raises(CommandError, match="unknown revision"):
        relatorio.migrations_from_diff("origin/nada")


def test_ida_e_volta_so_num_banco_descartavel(monkeypatch):
    """--test-rollback undoes migrations: never on a database with real data."""
    monkeypatch.delenv("DISPOSABLE_DATABASE", raising=False)
    producao = SimpleNamespace(settings_dict={"NAME": "kaladrius"})
    with pytest.raises(CommandError, match="banco descartável"):
        relatorio.disposable_database(producao)
    relatorio.disposable_database(SimpleNamespace(settings_dict={"NAME": "test_kaladrius"}))
    monkeypatch.setenv("DISPOSABLE_DATABASE", "1")
    relatorio.disposable_database(producao)


@pytest.mark.django_db
def test_comando_recusa_testar_volta_fora_do_banco_descartavel(monkeypatch):
    monkeypatch.delenv("DISPOSABLE_DATABASE", raising=False)
    monkeypatch.setitem(connection.settings_dict, "NAME", "kaladrius")
    chamadas = []
    monkeypatch.setattr(relatorio, "analyze", lambda chaves: chamadas.append(chaves) or [])
    from django.core.management import call_command

    with pytest.raises(CommandError, match="banco descartável"):
        call_command("migrations_report", "convenios.0003_x", testar_volta=True)
    assert chamadas == []  # refused before anything ran


@pytest.mark.django_db
def test_ida_e_volta_com_falha_ao_reaplicar(monkeypatch):
    """When undoing fails and applying again fails too, the failures are reported, not raised:
    the report must still be written and say why."""
    chamadas = []

    def migrar(*args):
        chamadas.append(args)
        if len(chamadas) > 1:
            raise RuntimeError(f"falhou {len(chamadas)}")

    monkeypatch.setattr(relatorio, "_migrate", migrar)
    falhas = relatorio.round_trip([HEALTH_PLANS, ("core", "0001_initial")])
    assert [onde for onde, _error in falhas] == [
        "`convenios` back to `0002_ordem_alfabetica` and forward again",
        "applying every migration again after that failure (the database is left half-migrated: "
        "the remaining apps were not tested)",
    ]
    assert falhas[1][1] == "RuntimeError: falhou 3"
    assert len(chamadas) == 3  # core was not tried on a half-migrated database


@pytest.mark.django_db
def test_ida_e_volta_quando_nem_aplica(monkeypatch):
    """A migration that conflicts with the base branch fails on the first migrate."""

    def migrar(*args):
        raise RuntimeError("conflito")

    monkeypatch.setattr(relatorio, "_migrate", migrar)
    assert relatorio.round_trip([HEALTH_PLANS]) == [
        ("applying every migration", "RuntimeError: conflito")
    ]


@pytest.mark.django_db(transaction=True)
def test_ida_e_volta_de_uma_migracao_real():
    assert relatorio.round_trip([HEALTH_PLANS]) == []


@pytest.mark.django_db(transaction=True)
def test_comando_completo_com_ida_e_volta(tmp_path):
    """The command as CI runs it (it once failed: an option hid the function of the same name)."""
    from django.core.management import call_command

    arquivo, comentario = tmp_path / "relatorio.md", tmp_path / "comentario.md"
    saida = StringIO()
    call_command(
        "migrations_report",
        f"{HEALTH_PLANS[0]}.{HEALTH_PLANS[1]}",
        testar_volta=True,
        saida=str(arquivo),
        comentario=str(comentario),
        stdout=saida,
    )
    assert "Back and forth tested" in arquivo.read_text() == saida.getvalue()
    assert comentario.read_text() == arquivo.read_text()  # small: the same report
