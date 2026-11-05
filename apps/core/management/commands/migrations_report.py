"""Report of the database migrations a pull request adds (decision 139): the SQL each one runs in
production, the operations that lose data or that the previous version of the system cannot
run with (the automatic rollback, decision 135, puts the previous code back but never undoes a
migration), the migrations already in the base branch that it edits or deletes (production
never runs an applied migration again) and, with --test-rollback, a test that each new one can
be applied, undone and applied again. CI posts the report as a comment on the pull request
(.github/workflows/migrations.yml).

    python manage.py migrations_report --base origin/main [--test-rollback]
    python manage.py migrations_report convenios.0003_seguros_de_cada_pais

--test-rollback undoes migrations on the database it runs on, so it only runs on a throwaway
one: the test database, or with DISPOSABLE_DATABASE=1, as in CI.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.db.migrations import operations as ops
from django.db.migrations.loader import MigrationLoader
from django.db.models.fields import NOT_PROVIDED

FILE_NAME = re.compile(r"^apps/(\w+)/migrations/(\d{4}_\w+)\.py$")

# GitHub refuses a comment longer than 65,536 characters; the marker and a margin fit below this.
COMMENT_LIMIT = 60_000

# Kinds of attention, from the most serious.
DELETES = "deletes data"
BREAKS_ROLLBACK = "the previous version of the system does not work with it"
NO_ROLLBACK = "cannot be undone"
REVIEW = "review"
CHANGED = "changes a migration production already applied"


@dataclass
class Alert:
    kind: str
    text: str


@dataclass
class MigrationEntry:
    app: str
    name: str
    sql: str = ""
    operacoes: list = field(default_factory=list)  # (description, [Alerta])

    @property
    def key(self):
        return f"{self.app}.{self.name}"

    @property
    def alerts(self):
        return [alerta for _descricao, alerts in self.operacoes for alerta in alerts]


def _labels():
    """The label of each app folder: apps/schedule keeps the label "agenda" (decision 145), and
    the database, the migrations and production know an app by its label."""
    return {
        config.name.removeprefix("apps."): config.label
        for config in django_apps.get_app_configs()
        if config.name.startswith("apps.")
    }


def _git(*args):
    git = shutil.which("git") or "git"
    resultado = subprocess.run(  # noqa: S603 (fixed git command, ref given by CI)
        [git, *args], capture_output=True, text=True, check=False
    )
    if resultado.returncode:
        raise CommandError(f"git {args[0]} falhou: {resultado.stderr.strip()}")
    return resultado.stdout


def migrations_from_diff(base):
    """The migration files this branch changed since `base` (a git ref): (added, changed). Added
    is the sorted (app label, name) list of the new ones; changed, the (app label, name, status)
    of those already in `base` that it edits (M) or deletes (D). A rename counts as a deletion
    and an addition (--no-renames): production recorded the old name and runs the new one as
    new. A migration moved with its app's folder keeps its label and name, so production sees
    the same migration: unchanged when its text is the same, edited (M) otherwise."""
    rotulos = _labels()
    novas, apagadas, alteradas = {}, {}, []
    for row in _git("diff", "--name-status", "--no-renames", f"{base}...HEAD").splitlines():
        status, _tab, path = row.partition("\t")
        if not (m := FILE_NAME.match(path)):
            continue
        key = (rotulos.get(m[1], m[1]), m[2])
        if status == "A":
            novas[key] = path
        elif status == "D":
            apagadas[key] = path
        else:
            alteradas.append((*key, status[:1]))
    for key in novas.keys() & apagadas.keys():
        before = _git("show", f"{base}:{apagadas.pop(key)}")
        if before != _git("show", f"HEAD:{novas.pop(key)}"):
            alteradas.append((*key, "M"))
    alteradas += [(*key, "D") for key in apagadas]
    return sorted(novas), sorted(alteradas)


def _field(estado, app, modelo, name):
    try:
        return estado.apps.get_model(app, modelo)._meta.get_field(name)
    except LookupError:
        return None


def _tables(estado, app, modelo):
    """The model's table and its many-to-many tables: what a rename may move."""
    try:
        meta = estado.apps.get_model(app, modelo)._meta
    except LookupError:
        return None
    return [meta.db_table, *(model_field.m2m_db_table() for model_field in meta.local_many_to_many)]


def _name_only(operacao, app, before):
    """A rename that keeps the table and columns (decision 156: Meta.db_table, db_column): only
    the name in the code changes, the database and the previous version see nothing."""
    after = _after(operacao, app, before)
    if isinstance(operacao, ops.RenameModel):
        tables = _tables(before, app, operacao.old_name), _tables(after, app, operacao.new_name)
    elif isinstance(operacao, ops.AlterModelTable):
        tables = _tables(before, app, operacao.name), _tables(after, app, operacao.name)
    else:  # RenameField
        old = _field(before, app, operacao.model_name, operacao.old_name)
        new = _field(after, app, operacao.model_name, operacao.new_name)
        tables = [getattr(old, "column", None)], [getattr(new, "column", None)]
    return None not in tables and tables[0] == tables[1]


def _after(operacao, app, before):
    """The project state after `operacao`, leaving `antes` as it was."""
    after = before.clone()
    operacao.state_forwards(app, after)
    return after


def _only_grows(tipo_antigo, new_appointment_type):
    """varchar(6) -> varchar(20): a longer text column keeps every value (a shorter one may not)."""
    old = re.fullmatch(r"varchar\((\d+)\)", tipo_antigo or "")
    new = re.fullmatch(r"varchar\((\d+)\)", new_appointment_type or "")
    return bool(old and new and int(new[1]) >= int(old[1]))


def _required_column_without_default(model_field):
    """A column the previous version leaves out of its INSERTs and the database cannot fill:
    NOT NULL and no db_default (Django's Python `default` only fills the existing rows; the
    column is left with no default in the database)."""
    return (
        not model_field.many_to_many
        and not isinstance(model_field, models.GeneratedField)
        and not model_field.null
        and model_field.db_default is NOT_PROVIDED
    )


def operation_alerts(operacao, app, before, conexao=connection):
    """What deserves attention in one operation, given the project state before it."""
    if isinstance(operacao, ops.SeparateDatabaseAndState):
        # Only its database operations touch the database; they run one after the other.
        alerts, estado = [], before
        for sub in operacao.database_operations:
            alerts += operation_alerts(sub, app, estado, conexao)
            estado = _after(sub, app, estado)
        return alerts
    alerts = []
    if isinstance(operacao, ops.RenameModel | ops.AlterModelTable | ops.RenameField) and _name_only(
        operacao, app, before
    ):
        pass
    elif isinstance(operacao, ops.RemoveField):
        alerts.append(Alert(DELETES, f"drops column `{operacao.name}` of `{operacao.model_name}`"))
        alerts.append(Alert(BREAKS_ROLLBACK, "the previous version still reads that column"))
    elif isinstance(operacao, ops.DeleteModel):
        alerts.append(Alert(DELETES, f"drops table `{operacao.name}`"))
        alerts.append(Alert(BREAKS_ROLLBACK, "the previous version still reads that table"))
    elif isinstance(operacao, ops.RenameField):
        alerts.append(
            Alert(
                BREAKS_ROLLBACK,
                f"renames `{operacao.old_name}` to `{operacao.new_name}` in "
                f"`{operacao.model_name}`: the previous version uses the old name",
            )
        )
    elif isinstance(operacao, ops.RenameModel | ops.AlterModelTable):
        alerts.append(
            Alert(BREAKS_ROLLBACK, "renames a table: the previous version uses the old one")
        )
    elif isinstance(operacao, ops.AddField):
        if _required_column_without_default(operacao.field):
            alerts.append(
                Alert(
                    BREAKS_ROLLBACK,
                    f"adds required column `{operacao.model_name}.{operacao.name}` with no "
                    "database default: the previous version's inserts into that table fail "
                    "(use null=True or db_default)",
                )
            )
    elif isinstance(operacao, ops.AlterField):
        old = _field(before, app, operacao.model_name, operacao.name)
        # The field as it is in the model after the change: operacao.field is not attached to a
        # model, and a ForeignKey's related model is still a string there (no db_type).
        new = _field(_after(operacao, app, before), app, operacao.model_name, operacao.name)
        if old is not None and new is not None:
            tipo_antigo, new_appointment_type = old.db_type(conexao), new.db_type(conexao)
            if tipo_antigo != new_appointment_type and not _only_grows(
                tipo_antigo, new_appointment_type
            ):
                alerts.append(
                    Alert(
                        REVIEW,
                        f"changes `{operacao.model_name}.{operacao.name}` from "
                        f"{tipo_antigo} to {new_appointment_type}",
                    )
                )
            if old.null and not new.null:
                alerts.append(
                    Alert(
                        REVIEW,
                        f"makes `{operacao.model_name}.{operacao.name}` required: existing "
                        "empty values make it fail",
                    )
                )
                alerts.append(
                    Alert(BREAKS_ROLLBACK, "the previous version may still save it empty")
                )
    if not operacao.reversible:
        alerts.append(Alert(NO_ROLLBACK, f"{type(operacao).__name__} has no reverse operation"))
    return alerts


def analyze(chaves, loader=None):
    """A Migracao, with its SQL and the attention points of each operation, per (app, name)."""
    loader = loader or MigrationLoader(connection, ignore_no_migrations=True)
    resultado = []
    for app, name in chaves:
        if (app, name) not in loader.disk_migrations:
            raise CommandError(f"Migração {app}.{name} não encontrada.")
        migracao = loader.disk_migrations[(app, name)]
        # The state right before this migration: every migration it depends on, not itself.
        estado = loader.project_state((app, name), at_end=False)
        item = MigrationEntry(app, name)
        for operacao in migracao.operations:
            item.operacoes.append((operacao.describe(), operation_alerts(operacao, app, estado)))
            estado = _after(operacao, app, estado)
        saida = StringIO()
        call_command("sqlmigrate", app, name, stdout=saida)
        item.sql = saida.getvalue().strip()
        resultado.append(item)
    return resultado


def disposable_database(conexao=connection):
    """--test-rollback undoes migrations: an AddField undone loses that column's data. Only on
    the test database or where DISPOSABLE_DATABASE=1 says the database is throwaway (CI)."""
    name = str(conexao.settings_dict["NAME"])
    if os.environ.get("DISPOSABLE_DATABASE") == "1" or name.startswith("test_"):
        return
    raise CommandError(
        f"--test-rollback desfaz migrações no banco {name}, e os dados delas se perdem. Só num "
        "banco descartável: o de testes, ou com DISPOSABLE_DATABASE=1 (o CI)."
    )


def _migrate(*args):
    call_command("migrate", *args, interactive=False, verbosity=0, stdout=StringIO())


def _error(error):
    return f"{type(error).__name__}: {error}"


def round_trip(chaves):
    """Applies everything, undoes each app's new migrations and applies them again. Returns the
    failures, as (what was being done, error); empty when everything went back and forth."""
    disposable_database()
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    try:
        _migrate()
    except Exception as error:  # noqa: BLE001 (any failure is the answer)
        return [("applying every migration", _error(error))]
    falhas = []
    for app in sorted({app for app, _nome in chaves}):
        primeira = min(name for a, name in chaves if a == app)
        country = [p.key for p in loader.graph.node_map[(app, primeira)].parents if p.key[0] == app]
        alvo = country[0][1] if country else "zero"
        try:
            _migrate(app, alvo)
            _migrate()
        except Exception as error:  # noqa: BLE001
            falhas.append((f"`{app}` back to `{alvo}` and forward again", _error(error)))
            try:
                _migrate()
            except Exception as erro_de_novo:  # noqa: BLE001
                falhas.append(
                    (
                        "applying every migration again after that failure (the database is "
                        "left half-migrated: the remaining apps were not tested)",
                        _error(erro_de_novo),
                    )
                )
                break
    return falhas


def _migration_lines(migracao, com_sql):
    rows = [f"### `{migracao.key}`"]
    rows += [
        f"- {description}" + "".join(f" — ⚠️ {a.kind}" for a in alertas_op)
        for description, alertas_op in migracao.operacoes
    ]
    if com_sql:
        rows += ["", "<details><summary>SQL</summary>", "", "```sql", migracao.sql, "```", ""]
        rows += ["</details>"]
    return [*rows, ""]


def _changed(alteradas):
    feito = {"D": "deleted"}
    return [
        f"- **{app}.{name}** — {CHANGED}: {feito.get(status, 'edited')}, but it is already in "
        "the base branch, and production never runs an applied migration again. Put the change "
        "in a new migration."
        for app, name, status in alteradas
    ]


def markdown(migracoes, falhas=None, alteradas=(), limit=None):
    """The report, in English, for the pull request comment and the CI summary. With `limite`
    (a comment's size), the SQL is left out when the report would be longer, and as a last
    resort the report is cut."""
    text = _markdown(migracoes, falhas, alteradas, com_sql=True)
    if limit is None or len(text) <= limit:
        return text
    text = _markdown(migracoes, falhas, alteradas, com_sql=False)
    if len(text) <= limit:
        return text
    corte = "\n\n… (cut: the full report is in the run's summary)\n"
    return text[: limit - len(corte)] + corte


def _markdown(migracoes, falhas, alteradas, com_sql):
    rows = ["## Database migrations in this pull request", ""]
    if not migracoes and not alteradas:
        return "\n".join([*rows, "No new migration: the database does not change.", ""])
    alerts = [(m, a) for m in migracoes for a in m.alerts]
    if migracoes:
        rows.append(
            f"**{len(migracoes)} new migration(s)**, applied automatically when the new version "
            "starts (`python manage.py migrate`). The automatic rollback puts the previous code "
            "back but never undoes a migration."
        )
    else:
        rows.append("No new migration, but existing ones changed.")
    rows.append("")
    if alerts or alteradas:
        rows.append("### ⚠️ Needs attention")
        rows += _changed(alteradas)
        rows += [f"- **{m.key}** — {a.kind}: {a.text}" for m, a in alerts]
    else:
        rows.append("✅ No operation deletes data or breaks the previous version.")
    rows.append("")
    if falhas is not None:
        if falhas:
            rows.append("### ❌ Back and forth")
            rows += [f"- {onde}: {error}" for onde, error in falhas]
        else:
            rows.append(
                "✅ **Back and forth tested:** every new migration was applied, undone and "
                "applied again on PostgreSQL."
            )
        rows.append("")
    if migracoes and not com_sql:
        rows += [
            "_The SQL is left out: the report is longer than a pull request comment allows. "
            "It is in full in the run's summary._",
            "",
        ]
    for migracao in migracoes:
        rows += _migration_lines(migracao, com_sql)
    return "\n".join(rows)


class Command(BaseCommand):
    help = "Report of new migrations: SQL, operations needing attention and back-and-forth test."

    def add_arguments(self, parser):
        parser.add_argument(
            "migracoes", metavar="migrations", nargs="*", help="app.migration (default: --base)"
        )
        parser.add_argument("--base", help="git ref to compare with, e.g. origin/main")
        parser.add_argument(
            "--test-rollback",
            dest="testar_volta",
            action="store_true",
            help="undo and redo them (throwaway database only: tests, or DISPOSABLE_DATABASE=1)",
        )
        parser.add_argument("--output", dest="saida", help="also write the report to this file")
        parser.add_argument(
            "--comment",
            dest="comentario",
            help="also write it, cut to fit a pull request comment, to this file",
        )

    def handle(self, *args, migracoes, base, testar_volta, saida, comentario, **options):
        if migracoes:
            chaves, alteradas = [tuple(m.split(".", 1)) for m in migracoes], []
        elif base:
            chaves, alteradas = migrations_from_diff(base)
        else:
            raise CommandError("Informe as migrações ou --base.")
        if testar_volta:
            disposable_database()  # before anything, not after the analysis
        analisadas = analyze(chaves)
        falhas = round_trip(chaves) if testar_volta and chaves else None
        relatorio = markdown(analisadas, falhas, alteradas)
        if saida:
            with open(saida, "w", encoding="utf-8") as file:
                file.write(relatorio)
        if comentario:
            with open(comentario, "w", encoding="utf-8") as file:
                file.write(markdown(analisadas, falhas, alteradas, limit=COMMENT_LIMIT))
        self.stdout.write(relatorio)
        if falhas:
            raise CommandError("O teste de ida e volta falhou.")
