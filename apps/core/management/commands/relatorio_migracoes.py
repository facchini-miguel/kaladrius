"""Report of the database migrations a pull request adds (decision 139): the SQL each one runs in
production, the operations that lose data or that the previous version of the system cannot
run with (the automatic rollback, decision 135, puts the previous code back but never undoes a
migration), and, with --testar-volta, a test that each one can be applied, undone and applied
again. CI posts the report as a comment on the pull request (.github/workflows/migracoes.yml).

    python manage.py relatorio_migracoes --base origin/main [--testar-volta]
    python manage.py relatorio_migracoes convenios.0003_seguros_de_cada_pais
"""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations import operations as ops
from django.db.migrations.loader import MigrationLoader

ARQUIVO = re.compile(r"^apps/(\w+)/migrations/(\d{4}_\w+)\.py$")

# Kinds of attention, from the most serious.
APAGA = "deletes data"
QUEBRA_VOLTA = "the previous version of the system does not work with it"
SEM_VOLTA = "cannot be undone"
REVISAR = "review"


@dataclass
class Alerta:
    tipo: str
    texto: str


@dataclass
class Migracao:
    app: str
    nome: str
    sql: str = ""
    operacoes: list = field(default_factory=list)  # (description, [Alerta])

    @property
    def chave(self):
        return f"{self.app}.{self.nome}"

    @property
    def alertas(self):
        return [alerta for _descricao, alertas in self.operacoes for alerta in alertas]


def migracoes_novas(base):
    """(app, name) of the migration files added since `base` (a git ref), in order."""
    git = shutil.which("git") or "git"
    resultado = subprocess.run(  # noqa: S603 (fixed git command, ref given by CI)
        [git, "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode:
        raise CommandError(f"git diff falhou: {resultado.stderr.strip()}")
    novas = [m.groups() for linha in resultado.stdout.split() if (m := ARQUIVO.match(linha))]
    return sorted(novas)


def _campo(estado, app, modelo, nome):
    try:
        return estado.apps.get_model(app, modelo)._meta.get_field(nome)
    except LookupError:
        return None


def _so_aumenta(tipo_antigo, tipo_novo):
    """varchar(6) -> varchar(20): a longer text column keeps every value (a shorter one may not)."""
    antigo = re.fullmatch(r"varchar\((\d+)\)", tipo_antigo or "")
    novo = re.fullmatch(r"varchar\((\d+)\)", tipo_novo or "")
    return bool(antigo and novo and int(novo[1]) >= int(antigo[1]))


def alertas_da_operacao(operacao, app, antes, conexao=connection):
    """What deserves attention in one operation, given the project state before it."""
    alertas = []
    if isinstance(operacao, ops.RemoveField):
        alertas.append(Alerta(APAGA, f"drops column `{operacao.name}` of `{operacao.model_name}`"))
        alertas.append(Alerta(QUEBRA_VOLTA, "the previous version still reads that column"))
    elif isinstance(operacao, ops.DeleteModel):
        alertas.append(Alerta(APAGA, f"drops table `{operacao.name}`"))
    elif isinstance(operacao, ops.RenameField):
        alertas.append(
            Alerta(
                QUEBRA_VOLTA,
                f"renames `{operacao.old_name}` to `{operacao.new_name}` in "
                f"`{operacao.model_name}`: the previous version uses the old name",
            )
        )
    elif isinstance(operacao, ops.RenameModel) or isinstance(operacao, ops.AlterModelTable):
        alertas.append(
            Alerta(QUEBRA_VOLTA, "renames a table: the previous version uses the old one")
        )
    elif isinstance(operacao, ops.AlterField):
        antigo = _campo(antes, app, operacao.model_name, operacao.name)
        novo = operacao.field
        if antigo is not None:
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
    if not operacao.reversible:
        alertas.append(Alerta(SEM_VOLTA, f"{type(operacao).__name__} has no reverse operation"))
    return alertas


def analisar(chaves, loader=None):
    """A Migracao, with its SQL and the attention points of each operation, per (app, name)."""
    loader = loader or MigrationLoader(connection, ignore_no_migrations=True)
    resultado = []
    for app, nome in chaves:
        if (app, nome) not in loader.disk_migrations:
            raise CommandError(f"Migração {app}.{nome} não encontrada.")
        migracao = loader.disk_migrations[(app, nome)]
        # The state right before this migration: every migration it depends on, not itself.
        antes = loader.project_state((app, nome), at_end=False)
        item = Migracao(app, nome)
        estado = antes
        for operacao in migracao.operations:
            item.operacoes.append((operacao.describe(), alertas_da_operacao(operacao, app, estado)))
            estado = estado.clone()
            operacao.state_forwards(app, estado)
        saida = StringIO()
        call_command("sqlmigrate", app, nome, stdout=saida)
        item.sql = saida.getvalue().strip()
        resultado.append(item)
    return resultado


def testar_volta(chaves, saida=None):
    """Applies everything, undoes each app's new migrations and applies them again. Returns the
    (app, target) pairs that failed, with the error."""
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    silencio = StringIO()
    call_command("migrate", interactive=False, verbosity=0, stdout=silencio)
    falhas = []
    for app in sorted({app for app, _nome in chaves}):
        primeira = min(nome for a, nome in chaves if a == app)
        pais = [p.key for p in loader.graph.node_map[(app, primeira)].parents if p.key[0] == app]
        alvo = pais[0][1] if pais else "zero"
        try:
            call_command("migrate", app, alvo, interactive=False, verbosity=0, stdout=silencio)
            call_command("migrate", interactive=False, verbosity=0, stdout=silencio)
        except Exception as erro:  # noqa: BLE001 (any failure is the answer)
            falhas.append((app, alvo, f"{type(erro).__name__}: {erro}"))
            call_command("migrate", interactive=False, verbosity=0, stdout=silencio)
    return falhas


def markdown(migracoes, falhas=None):
    """The report, in English, for the pull request comment and the CI summary."""
    linhas = ["## Database migrations in this pull request", ""]
    if not migracoes:
        return "\n".join([*linhas, "No new migration: the database does not change.", ""])
    alertas = [(m, a) for m in migracoes for a in m.alertas]
    linhas.append(
        f"**{len(migracoes)} new migration(s)**, applied automatically when the new version "
        "starts (`python manage.py migrate`). The automatic rollback puts the previous code "
        "back but never undoes a migration."
    )
    linhas.append("")
    if alertas:
        linhas.append("### ⚠️ Needs attention")
        linhas += [f"- **{m.chave}** — {a.tipo}: {a.texto}" for m, a in alertas]
    else:
        linhas.append("✅ No operation deletes data or breaks the previous version.")
    linhas.append("")
    if falhas is not None:
        if falhas:
            linhas.append("### ❌ Back and forth")
            linhas += [f"- `{app}` back to `{alvo}`: {erro}" for app, alvo, erro in falhas]
        else:
            linhas.append(
                "✅ **Back and forth tested:** every new migration was applied, undone and "
                "applied again on PostgreSQL."
            )
        linhas.append("")
    for migracao in migracoes:
        linhas.append(f"### `{migracao.chave}`")
        linhas += [
            f"- {descricao}" + "".join(f" — ⚠️ {a.tipo}" for a in alertas_op)
            for descricao, alertas_op in migracao.operacoes
        ]
        linhas += ["", "<details><summary>SQL</summary>", "", "```sql", migracao.sql, "```", ""]
        linhas += ["</details>", ""]
    return "\n".join(linhas)


class Command(BaseCommand):
    help = "Report of new migrations: SQL, operations needing attention and back-and-forth test."

    def add_arguments(self, parser):
        parser.add_argument("migracoes", nargs="*", help="app.migration (default: --base)")
        parser.add_argument("--base", help="git ref to compare with, e.g. origin/main")
        parser.add_argument("--testar-volta", action="store_true", help="undo and redo them")
        parser.add_argument("--saida", help="also write the report to this file")

    def handle(self, *args, migracoes, base, testar_volta, saida, **options):
        if migracoes:
            chaves = [tuple(m.split(".", 1)) for m in migracoes]
        elif base:
            chaves = migracoes_novas(base)
        else:
            raise CommandError("Informe as migrações ou --base.")
        analisadas = analisar(chaves)
        falhas = testar_volta(chaves) if testar_volta and chaves else None
        relatorio = markdown(analisadas, falhas)
        if saida:
            with open(saida, "w", encoding="utf-8") as arquivo:
                arquivo.write(relatorio)
        self.stdout.write(relatorio)
        if falhas:
            raise CommandError("Uma migração nova não pode ser desfeita.")
