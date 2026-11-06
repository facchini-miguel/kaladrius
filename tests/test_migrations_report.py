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


def _before(app, name):
    return MigrationLoader(connection).project_state((app, name), at_end=False)


def _types(alerts):
    return [health_alert.kind for health_alert in alerts]


def _alerts(operation):
    return _types(relatorio.operation_alerts(operation, "convenios", _before(*HEALTH_PLANS)))


@pytest.mark.django_db
def test_operations_that_delete_or_break_rollback():
    remove_ = migrations.RemoveField("carteirinha", "titular")
    assert _alerts(remove_) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    # The previous version still queries the dropped table: every page using it would fail.
    table = migrations.DeleteModel("Carteirinha")
    assert _alerts(table) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    rename = migrations.RenameField("convenio", "nome", "nome_novo")
    assert relatorio.BREAKS_ROLLBACK in _alerts(rename)


@pytest.mark.django_db
def test_rename_keeping_table_and_column_does_not_warn():
    """Decision 156: renamed in the code only, the table and column kept, nothing reaches the
    database; the previous version still works."""
    before = _before(*HEALTH_PLANS)
    pin_ = migrations.AlterModelTable("convenio", "convenios_convenio")
    assert relatorio.operation_alerts(pin_, "convenios", before) == []
    before = relatorio._after(pin_, "convenios", before)
    template_ = migrations.RenameModel("Convenio", "HealthPlan")
    assert relatorio.operation_alerts(template_, "convenios", before) == []
    # The table follows the model's name when it is not pinned: the previous version breaks.
    loose_one = migrations.RenameModel("Carteirinha", "Card")
    assert _types(relatorio.operation_alerts(loose_one, "convenios", before)) == [
        relatorio.BREAKS_ROLLBACK
    ]
    before = relatorio._after(template_, "convenios", before)
    column = migrations.AlterField(
        "healthplan", "nome", models.CharField(max_length=100, db_column="nome")
    )
    before = relatorio._after(column, "convenios", before)
    field = migrations.RenameField("healthplan", "nome", "name")
    assert relatorio.operation_alerts(field, "convenios", before) == []


@pytest.mark.django_db
def test_irreversible_operations_and_altered_fields():
    without_return = migrations.RunPython(lambda apps, schema: None)
    assert _alerts(without_return) == [relatorio.NO_ROLLBACK]
    with_return = migrations.RunPython(lambda a, s: None, migrations.RunPython.noop)
    assert _alerts(with_return) == []
    # convenio.nome is varchar(200): shorter or another type deserve a look.
    assert _alerts(migrations.AlterField("convenio", "nome", models.CharField(max_length=50))) == [
        relatorio.REVIEW
    ]
    assert (
        _alerts(migrations.AlterField("convenio", "nome", models.CharField(max_length=300))) == []
    )
    assert _alerts(migrations.AlterField("convenio", "nome", models.IntegerField())) == [
        relatorio.REVIEW
    ]
    # carteirinha.validade may be empty: made required, existing rows and the previous version
    # (which may still save it empty) fail.
    is_required = migrations.AlterField("carteirinha", "validade", models.DateField())
    assert _alerts(is_required) == [relatorio.REVIEW, relatorio.BREAKS_ROLLBACK]


@pytest.mark.django_db
def test_altering_a_foreign_key():
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
    assert _alerts(key) == []


@pytest.mark.django_db
def test_new_required_column():
    """The previous version's inserts leave a new column out: NOT NULL with no database default
    makes them fail (Django's Python default only fills the existing rows)."""
    is_required = migrations.AddField(
        "convenio", "sigla", models.CharField(max_length=5, default="")
    )
    assert _alerts(is_required) == [relatorio.BREAKS_ROLLBACK]
    empty = migrations.AddField("convenio", "sigla", models.CharField(max_length=5, null=True))
    assert _alerts(empty) == []
    with_default = migrations.AddField(
        "convenio", "sigla", models.CharField(max_length=5, db_default="")
    )
    assert _alerts(with_default) == []
    many_items = migrations.AddField(
        "convenio", "outros", models.ManyToManyField("convenios.convenio")
    )
    assert _alerts(many_items) == []


@pytest.mark.django_db
def test_separate_database_and_state_is_inspected():
    """Only the database operations reach the database: a column dropped there is flagged."""
    hidden = migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RemoveField("carteirinha", "titular")],
        state_operations=[],
    )
    assert _alerts(hidden) == [relatorio.DELETES, relatorio.BREAKS_ROLLBACK]
    state_only = migrations.SeparateDatabaseAndState(
        state_operations=[migrations.RemoveField("carteirinha", "titular")]
    )
    assert _alerts(state_only) == []


@pytest.mark.django_db
def test_report_of_a_real_migration():
    """convenios.0003 renamed registro_ans and added two required columns with no database
    default: the previous version would not work with it."""
    (migration,) = relatorio.analyze([HEALTH_PLANS])
    assert 'RENAME COLUMN "registro_ans" TO "registro"' in migration.sql
    # varchar 6 -> 20 is fine; the rename and carteirinha.grupo and .beneficiario are not.
    assert _types(migration.alerts) == [relatorio.BREAKS_ROLLBACK] * 3
    text_ = relatorio.markdown([migration], falhas=[])
    assert "### ⚠️ Needs attention" in text_ and "convenios.0003_seguros_de_cada_pais" in text_
    assert "Back and forth tested" in text_ and "```sql" in text_


def test_report_without_migrations():
    assert "No new migration" in relatorio.markdown([])


def test_report_of_altered_applied_migration():
    text_ = relatorio.markdown(
        [], alteradas=[("convenios", "0003_x", "M"), ("core", "0001_y", "D")]
    )
    assert "### ⚠️ Needs attention" in text_
    assert f"**convenios.0003_x** — {relatorio.CHANGED}: edited" in text_
    assert f"**core.0001_y** — {relatorio.CHANGED}: deleted" in text_
    assert "the database does not change" not in text_


def test_comment_fits_github_limit():
    """GitHub refuses a comment over 65,536 characters: the SQL is left out first, then cut."""
    large = relatorio.MigrationEntry("convenios", "0004_x", sql="SELECT 1;\n" * 10_000)
    large.operacoes = [("Add field x", [])]
    full = relatorio.markdown([large])
    assert len(full) > relatorio.COMMENT_LIMIT and "```sql" in full
    short = relatorio.markdown([large], limit=relatorio.COMMENT_LIMIT)
    assert len(short) <= relatorio.COMMENT_LIMIT
    assert "```sql" not in short and "The SQL is left out" in short and "Add field x" in short
    many = [
        relatorio.MigrationEntry("a", f"{n:04}_x", operacoes=[("y" * 1000, [])]) for n in range(80)
    ]
    cut = relatorio.markdown(many, limit=relatorio.COMMENT_LIMIT)
    assert len(cut) <= relatorio.COMMENT_LIMIT and cut.endswith("summary)\n")


def test_diff_migrations_reads_git(monkeypatch):
    """Folders become labels (apps/health_plans is "convenios", decision 145), and a migration
    moved with its folder is unchanged when its text is the same, edited when it is not."""
    output = (
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
    texts = {
        "origin/main:apps/agenda/migrations/0001_initial.py": "igual",
        "HEAD:apps/schedule/migrations/0001_initial.py": "igual",
        "origin/main:apps/agenda/migrations/0003_agendamento.py": "import apps.agenda.models",
        "HEAD:apps/schedule/migrations/0003_agendamento.py": "import apps.schedule.models",
    }

    def git(args, **kwargs):
        if args[1] == "show":
            return subprocess.CompletedProcess(args, 0, stdout=texts[args[2]], stderr="")
        assert args[1:4] == ["diff", "--name-status", "--no-renames"]
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(relatorio.subprocess, "run", git)
    assert relatorio.migrations_from_diff("origin/main") == (
        [("convenios", "0004_x"), ("core", "0019_y")],
        [
            ("agenda", "0003_agendamento", "M"),
            ("convenios", "0003_seguros_de_cada_pais", "M"),
            ("core", "0002_z", "D"),
        ],
    )


def test_diff_migrations_when_git_fails(monkeypatch):
    def git(args, **kwargs):
        return subprocess.CompletedProcess(args, 128, stdout="", stderr="unknown revision")

    monkeypatch.setattr(relatorio.subprocess, "run", git)
    with pytest.raises(CommandError, match="unknown revision"):
        relatorio.migrations_from_diff("origin/nada")


def test_round_trip_only_on_disposable_database(monkeypatch):
    """--test-rollback undoes migrations: never on a database with real data."""
    monkeypatch.delenv("DISPOSABLE_DATABASE", raising=False)
    production = SimpleNamespace(settings_dict={"NAME": "kaladrius"})
    with pytest.raises(CommandError, match="banco descartável"):
        relatorio.disposable_database(production)
    relatorio.disposable_database(SimpleNamespace(settings_dict={"NAME": "test_kaladrius"}))
    monkeypatch.setenv("DISPOSABLE_DATABASE", "1")
    relatorio.disposable_database(production)


@pytest.mark.django_db
def test_command_refuses_rollback_test_outside_disposable_database(monkeypatch):
    monkeypatch.delenv("DISPOSABLE_DATABASE", raising=False)
    monkeypatch.setitem(connection.settings_dict, "NAME", "kaladrius")
    calls = []
    monkeypatch.setattr(relatorio, "analyze", lambda keys: calls.append(keys) or [])
    from django.core.management import call_command

    with pytest.raises(CommandError, match="banco descartável"):
        call_command("migrations_report", "convenios.0003_x", testar_volta=True)
    assert calls == []  # refused before anything ran


@pytest.mark.django_db
def test_round_trip_failing_to_reapply(monkeypatch):
    """When undoing fails and applying again fails too, the failures are reported, not raised:
    the report must still be written and say why."""
    calls = []

    def migrate(*args):
        calls.append(args)
        if len(calls) > 1:
            raise RuntimeError(f"falhou {len(calls)}")

    monkeypatch.setattr(relatorio, "_migrate", migrate)
    failures = relatorio.round_trip([HEALTH_PLANS, ("core", "0001_initial")])
    assert [where for where, _error in failures] == [
        "`convenios` back to `0002_ordem_alfabetica` and forward again",
        "applying every migration again after that failure (the database is left half-migrated: "
        "the remaining apps were not tested)",
    ]
    assert failures[1][1] == "RuntimeError: falhou 3"
    assert len(calls) == 3  # core was not tried on a half-migrated database


@pytest.mark.django_db
def test_round_trip_when_it_does_not_even_apply(monkeypatch):
    """A migration that conflicts with the base branch fails on the first migrate."""

    def migrate(*args):
        raise RuntimeError("conflito")

    monkeypatch.setattr(relatorio, "_migrate", migrate)
    assert relatorio.round_trip([HEALTH_PLANS]) == [
        ("applying every migration", "RuntimeError: conflito")
    ]


@pytest.mark.django_db
def test_round_trip_of_a_real_migration(monkeypatch):
    """Everything applied, the app taken back to before its first new migration, applied
    again. The migrations themselves go back and forth in the CI job that runs this report on
    every pull request with migrations (decision 180): here, only the steps."""
    calls = []
    monkeypatch.setattr(relatorio, "_migrate", lambda *args: calls.append(args))
    assert relatorio.round_trip([HEALTH_PLANS]) == []
    assert calls == [(), ("convenios", "0002_ordem_alfabetica"), ()]


@pytest.mark.django_db
def test_full_command_with_round_trip(tmp_path, monkeypatch):
    """The command as CI runs it (it once failed: an option hid the function of the same name).
    The migrations' real back and forth is the CI job's (decision 180)."""
    from django.core.management import call_command

    monkeypatch.setattr(relatorio, "_migrate", lambda *args: None)
    file_path, comment = tmp_path / "relatorio.md", tmp_path / "comentario.md"
    output = StringIO()
    call_command(
        "migrations_report",
        f"{HEALTH_PLANS[0]}.{HEALTH_PLANS[1]}",
        testar_volta=True,
        saida=str(file_path),
        comentario=str(comment),
        stdout=output,
    )
    assert "Back and forth tested" in file_path.read_text() == output.getvalue()
    assert comment.read_text() == file_path.read_text()  # small: the same report
