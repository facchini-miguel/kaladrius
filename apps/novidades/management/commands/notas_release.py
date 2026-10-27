from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from apps.novidades import releases


class Command(BaseCommand):
    help = (
        "Prints the GitHub release title or notes of a version, built from releases.yaml "
        "(English by default, the standard for GitHub releases)."
    )

    def add_arguments(self, parser):
        parser.add_argument("versao", help="Version, e.g. 0.14.0.")
        parser.add_argument("--idioma", default="en", choices=[c for c, _n in settings.LANGUAGES])
        parser.add_argument("--titulo", action="store_true", help="Print only the title.")

    def handle(self, *args, versao, idioma, titulo, **options):
        release = next((r for r in releases.todas() if r.versao == versao), None)
        if release is None:
            raise CommandError(f"Versão {versao} não está no releases.yaml.")
        with translation.override(idioma):
            if titulo:
                nome = f"{release.versao} – {release.titulo}" if release.titulo else release.versao
                self.stdout.write(nome)
                return
            for item in release.itens:
                self.stdout.write(f"- **{item.tipo_nome} · {item.modulo_nome}:** {item.texto}")
