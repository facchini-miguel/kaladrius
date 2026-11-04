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

ARQUIVO = re.compile(r"^apps/(\w+)/migrations/(\d{4}_\w+)\.py$")

# GitHub refuses a comment longer than 65,536 characters; the marker and a margin fit below this.
LIMITE_COMENTARIO = 60_000

# Kinds of attention, from the most serious.
APAGA = "deletes data"
QUEBRA_VOLTA = "the previous version of the system does not work with it"
SEM_VOLTA = "cannot be undone"
REVISAR = "review"
ALTERADA = "changes a migration production already applied"


@dataclass
class Alerta:
    kind: str
    texto: str


@dataclass
class Migracao:
    app: str
    name: str
    sql: str = ""
    operacoes: list = field(default_factory=list)  # (description, [Alerta])

    @property
    def chave(self):
        return f"{self.app}.{self.name}"

    @property
    def alertas(self):
        return [alerta for _descricao, alertas in self.operacoes for alerta in alertas]


def _rotulos():
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


def migracoes_do_diff(base):
    """The migration files this branch changed since `base` (a git ref): (added, changed). Added
    is the sorted (app label, name) list of the new ones; changed, the (app label, name, status)
    of those already in `base` that it edits (M) or deletes (D). A rename counts as a deletion
    and an addition (--no-renames): production recorded the old name and runs the new one as
    new. A migration moved with its app's folder keeps its label and name, so production sees
    the same migration: unchanged when its text is the same, edited (M) otherwise."""
    rotulos = _rotulos()
    novas, apagadas, alteradas = {}, {}, []
    for linha in _git("diff", "--name-status", "--no-renames", f"{base}...HEAD").splitlines():
        status, _tab, caminho = linha.partition("\t")
        if not (m := ARQUIVO.match(caminho)):
            continue
        chave = (rotulos.get(m[1], m[1]), m[2])
        if status == "A":
            novas[chave] = caminho
        elif status == "D":
            apagadas[chave] = caminho
        else:
            alteradas.append((*chave, status[:1]))
    for chave in novas.keys() & apagadas.keys():
        antes = _git("show", f"{base}:{apagadas.pop(chave)}")
        if antes != _git("show", f"HEAD:{novas.pop(chave)}"):
            alteradas.append((*chave, "M"))
    alteradas += [(*chave, "D") for chave in apagadas]
    return sorted(novas), sorted(alteradas)


def _campo(estado, app, modelo, name):
    try:
        return estado.apps.get_model(app, modelo)._meta.get_field(name)
    except LookupError:
        return None


def _tabelas(estado, app, modelo):
    """The model's table and its many-to-many tables: what a rename may move."""
    try:
        meta = estado.apps.get_model(app, modelo)._meta
    except LookupError:
        return None
    return [meta.db_table, *(campo.m2m_db_table() for campo in meta.local_many_to_many)]


def _so_o_nome(operacao, app, antes):
    """A rename that keeps the table and columns (decision 156: Meta.db_table, db_column): only
    the name in the code changes, the database and the previous version see nothing."""
    depois = _depois(operacao, app, antes)
    if isinstance(operacao, ops.RenameModel):
        tabelas = _tabelas(antes, app, operacao.old_name), _tabelas(depois, app, operacao.new_name)
    elif isinstance(operacao, ops.AlterModelTable):
        tabelas = _tabelas(antes, app, operacao.name), _tabelas(depois, app, operacao.name)
    else:  # RenameField
        antigo = _campo(antes, app, operacao.model_name, operacao.old_name)
        novo = _campo(depois, app, operacao.model_name, operacao.new_name)
        tabelas = [getattr(antigo, "column", None)], [getattr(novo, "column", None)]
    return None not in tabelas and tabelas[0] == tabelas[1]


def _depois(operacao, app, antes):
    """The project state after `operacao`, leaving `antes` as it was."""
    depois = antes.clone()
    operacao.state_forwards(app, depois)
    return depois


def _so_aumenta(tipo_antigo, tipo_novo):
    """varchar(6) -> varchar(20): a longer text column keeps every value (a shorter one may not)."""
    antigo = re.fullmatch(r"varchar\((\d+)\)", tipo_antigo or "")
    novo = re.fullmatch(r"varchar\((\d+)\)", tipo_novo or "")
    return bool(antigo and novo and int(novo[1]) >= int(antigo[1]))


def _coluna_obrigatoria_sem_default(campo):
    """A column the previous version leaves out of its INSERTs and the database cannot fill:
    NOT NULL and no db_default (Django's Python `default` only fills the existing rows; the
    column is left with no default in the database)."""
    return (
        not campo.many_to_many
        and not isinstance(campo, models.GeneratedField)
        and not campo.null
        and campo.db_default is NOT_PROVIDED
    )


def alertas_da_operacao(operacao, app, antes, conexao=connection):
    """What deserves attention in one operation, given the project state before it."""
    if isinstance(operacao, ops.SeparateDatabaseAndState):
        # Only its database operations touch the database; they run one after the other.
        alertas, estado = [], antes
        for sub in operacao.database_operations:
            alertas += alertas_da_operacao(sub, app, estado, conexao)
            estado = _depois(sub, app, estado)
        return alertas
    alertas = []
    if isinstance(operacao, ops.RenameModel | ops.AlterModelTable | ops.RenameField) and _so_o_nome(
        operacao, app, antes
    ):
        pass
    elif isinstance(operacao, ops.RemoveField):
        alertas.append(Alerta(APAGA, f"drops column `{operacao.name}` of `{operacao.model_name}`"))
        alertas.append(Alerta(QUEBRA_VOLTA, "the previous version still reads that column"))
    elif isinstance(operacao, ops.DeleteModel):
        alertas.append(Alerta(APAGA, f"drops table `{operacao.name}`"))
        alertas.append(Alerta(QUEBRA_VOLTA, "the previous version still reads that table"))
    elif isinstance(operacao, ops.RenameField):
        alertas.append(
            Alerta(
                QUEBRA_VOLTA,
                f"renames `{operacao.old_name}` to `{operacao.new_name}` in "
                f"`{operacao.model_name}`: the previous version uses the old name",
            )
        )
    elif isinstance(operacao, ops.RenameModel | ops.AlterModelTable):
        alertas.append(
            Alerta(QUEBRA_VOLTA, "renames a table: the previous version uses the old one")
        )
    elif isinstance(operacao, ops.AddField):
        if _coluna_obrigatoria_sem_default(operacao.field):
            alertas.append(
                Alerta(
                    QUEBRA_VOLTA,
                    f"adds required column `{operacao.model_name}.{operacao.name}` with no "
                    "database default: the previous version's inserts into that table fail "
                    "(use null=True or db_default)",
                )
            )
    elif isinstance(operacao, ops.AlterField):
        antigo = _campo(antes, app, operacao.model_name, operacao.name)
        # The field as it is in the model after the change: operacao.field is not attached to a
        # model, and a ForeignKey's related model is still a string there (no db_type).
        novo = _campo(_depois(operacao, app, antes), app, operacao.model_name, operacao.name)
        if antigo is not None and novo is not None:
            tipo_antigo, tipo_novo = antigo.db_type(conexao), novo.db_type(conexao)
            if tipo_antigo != tipo_novo and not _so_aumenta(tipo_antigo, tipo_novo):
                alertas.append(
                    Alerta(
                        REVISAR,
                        f"changes `{operacao.model_name}.{operacao.name}` from "
                        f"{tipo_antigo} to {tipo_novo}",
                    )
                )
            if antigo.null and not novo.null:
                alertas.append(
                    Alerta(
                        REVISAR,
                        f"makes `{operacao.model_name}.{operacao.name}` required: existing "
                        "empty values make it fail",
                    )
                )
                alertas.append(Alerta(QUEBRA_VOLTA, "the previous version may still save it empty"))
    if not operacao.reversible:
        alertas.append(Alerta(SEM_VOLTA, f"{type(operacao).__name__} has no reverse operation"))
    return alertas


def analisar(chaves, loader=None):
    """A Migracao, with its SQL and the attention points of each operation, per (app, name)."""
    loader = loader or MigrationLoader(connection, ignore_no_migrations=True)
    resultado = []
    for app, name in chaves:
        if (app, name) not in loader.disk_migrations:
            raise CommandError(f"Migração {app}.{name} não encontrada.")
        migracao = loader.disk_migrations[(app, name)]
        # The state right before this migration: every migration it depends on, not itself.
        estado = loader.project_state((app, name), at_end=False)
        item = Migracao(app, name)
        for operacao in migracao.operations:
            item.operacoes.append((operacao.describe(), alertas_da_operacao(operacao, app, estado)))
            estado = _depois(operacao, app, estado)
        saida = StringIO()
        call_command("sqlmigrate", app, name, stdout=saida)
        item.sql = saida.getvalue().strip()
        resultado.append(item)
    return resultado


def banco_descartavel(conexao=connection):
    """--test-rollback undoes migrations: an AddField undone loses that column's data. Only on
    the test database or where DISPOSABLE_DATABASE=1 says the database is throwaway (CI)."""
    name = str(conexao.settings_dict["NAME"])
    if os.environ.get("DISPOSABLE_DATABASE") == "1" or name.startswith("test_"):
        return
    raise CommandError(
        f"--test-rollback desfaz migrações no banco {name}, e os dados delas se perdem. Só num "
        "banco descartável: o de testes, ou com DISPOSABLE_DATABASE=1 (o CI)."
    )


def _migrar(*args):
    call_command("migrate", *args, interactive=False, verbosity=0, stdout=StringIO())


def _erro(erro):
    return f"{type(erro).__name__}: {erro}"


def ida_e_volta(chaves):
    """Applies everything, undoes each app's new migrations and applies them again. Returns the
    failures, as (what was being done, error); empty when everything went back and forth."""
    banco_descartavel()
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    try:
        _migrar()
    except Exception as erro:  # noqa: BLE001 (any failure is the answer)
        return [("applying every migration", _erro(erro))]
    falhas = []
    for app in sorted({app for app, _nome in chaves}):
        primeira = min(name for a, name in chaves if a == app)
        pais = [p.key for p in loader.graph.node_map[(app, primeira)].parents if p.key[0] == app]
        alvo = pais[0][1] if pais else "zero"
        try:
            _migrar(app, alvo)
            _migrar()
        except Exception as erro:  # noqa: BLE001
            falhas.append((f"`{app}` back to `{alvo}` and forward again", _erro(erro)))
            try:
                _migrar()
            except Exception as erro_de_novo:  # noqa: BLE001
                falhas.append(
                    (
                        "applying every migration again after that failure (the database is "
                        "left half-migrated: the remaining apps were not tested)",
                        _erro(erro_de_novo),
                    )
                )
                break
    return falhas


def _linhas_da_migracao(migracao, com_sql):
    linhas = [f"### `{migracao.chave}`"]
    linhas += [
        f"- {description}" + "".join(f" — ⚠️ {a.kind}" for a in alertas_op)
        for description, alertas_op in migracao.operacoes
    ]
    if com_sql:
        linhas += ["", "<details><summary>SQL</summary>", "", "```sql", migracao.sql, "```", ""]
        linhas += ["</details>"]
    return [*linhas, ""]


def _alteradas(alteradas):
    feito = {"D": "deleted"}
    return [
        f"- **{app}.{name}** — {ALTERADA}: {feito.get(status, 'edited')}, but it is already in "
        "the base branch, and production never runs an applied migration again. Put the change "
        "in a new migration."
        for app, name, status in alteradas
    ]


def markdown(migracoes, falhas=None, alteradas=(), limite=None):
    """The report, in English, for the pull request comment and the CI summary. With `limite`
    (a comment's size), the SQL is left out when the report would be longer, and as a last
    resort the report is cut."""
    texto = _markdown(migracoes, falhas, alteradas, com_sql=True)
    if limite is None or len(texto) <= limite:
        return texto
    texto = _markdown(migracoes, falhas, alteradas, com_sql=False)
    if len(texto) <= limite:
        return texto
    corte = "\n\n… (cut: the full report is in the run's summary)\n"
    return texto[: limite - len(corte)] + corte


def _markdown(migracoes, falhas, alteradas, com_sql):
    linhas = ["## Database migrations in this pull request", ""]
    if not migracoes and not alteradas:
        return "\n".join([*linhas, "No new migration: the database does not change.", ""])
    alertas = [(m, a) for m in migracoes for a in m.alertas]
    if migracoes:
        linhas.append(
            f"**{len(migracoes)} new migration(s)**, applied automatically when the new version "
            "starts (`python manage.py migrate`). The automatic rollback puts the previous code "
            "back but never undoes a migration."
        )
    else:
        linhas.append("No new migration, but existing ones changed.")
    linhas.append("")
    if alertas or alteradas:
        linhas.append("### ⚠️ Needs attention")
        linhas += _alteradas(alteradas)
        linhas += [f"- **{m.chave}** — {a.kind}: {a.texto}" for m, a in alertas]
    else:
        linhas.append("✅ No operation deletes data or breaks the previous version.")
    linhas.append("")
    if falhas is not None:
        if falhas:
            linhas.append("### ❌ Back and forth")
            linhas += [f"- {onde}: {erro}" for onde, erro in falhas]
        else:
            linhas.append(
                "✅ **Back and forth tested:** every new migration was applied, undone and "
                "applied again on PostgreSQL."
            )
        linhas.append("")
    if migracoes and not com_sql:
        linhas += [
            "_The SQL is left out: the report is longer than a pull request comment allows. "
            "It is in full in the run's summary._",
            "",
        ]
    for migracao in migracoes:
        linhas += _linhas_da_migracao(migracao, com_sql)
    return "\n".join(linhas)


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
            chaves, alteradas = migracoes_do_diff(base)
        else:
            raise CommandError("Informe as migrações ou --base.")
        if testar_volta:
            banco_descartavel()  # before anything, not after the analysis
        analisadas = analisar(chaves)
        falhas = ida_e_volta(chaves) if testar_volta and chaves else None
        relatorio = markdown(analisadas, falhas, alteradas)
        if saida:
            with open(saida, "w", encoding="utf-8") as arquivo:
                arquivo.write(relatorio)
        if comentario:
            with open(comentario, "w", encoding="utf-8") as arquivo:
                arquivo.write(markdown(analisadas, falhas, alteradas, limite=LIMITE_COMENTARIO))
        self.stdout.write(relatorio)
        if falhas:
            raise CommandError("O teste de ida e volta falhou.")
