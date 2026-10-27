import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.legado.dump import DumpInvalido
from apps.legado.importacao import ImportacaoRecusada, importar


class Command(BaseCommand):
    help = (
        "Imports patients, schedule and recalls from a dump of the legacy Odonto System "
        "into a new clinic. All or nothing. The dump has real patient data: keep it out of "
        "the repository and delete copies made on servers after the import."
    )

    def add_arguments(self, parser):
        parser.add_argument("arquivo", help="MySQL dump (.sql). Use - to read from stdin.")
        parser.add_argument("--clinica", required=True, help="Name of the clinic to create.")
        parser.add_argument(
            "--codificacao", default="utf-8", help="Dump encoding (default: utf-8)."
        )

    def handle(self, *args, arquivo, clinica, codificacao, **options):
        try:
            if arquivo == "-":
                texto = sys.stdin.buffer.read().decode(codificacao)
            else:
                texto = Path(arquivo).read_text(encoding=codificacao)
        except (OSError, UnicodeDecodeError) as erro:
            raise CommandError(f"Não foi possível ler o arquivo: {erro}") from erro

        try:
            relatorio = importar(texto, clinica)
        except (DumpInvalido, ImportacaoRecusada) as erro:
            raise CommandError(str(erro)) from erro

        self.stdout.write(self.style.SUCCESS(f"Importado na clínica “{relatorio.clinica.nome}”:"))
        self.stdout.write(f"  Profissionais: {relatorio.profissionais}")
        self.stdout.write(f"  Tipos de atendimento novos: {relatorio.tipos_criados}")
        self.stdout.write(f"  Pacientes: {relatorio.pacientes}")
        self.stdout.write(f"  Agendamentos: {relatorio.agendamentos}")
        self.stdout.write(f"  Rechamadas: {relatorio.rechamadas}")
        if relatorio.avisos:
            self.stdout.write("Avisos:")
            for aviso, total in sorted(relatorio.avisos.items()):
                self.stdout.write(f"  {total} × {aviso}")
        self.stdout.write(
            "Nenhum usuário foi importado: crie a equipe em Cadastros › Equipe "
            "(e vincule o administrador da clínica pelo admin do Django)."
        )
