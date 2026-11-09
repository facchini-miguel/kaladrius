from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from apps.whats_new import releases


class Command(BaseCommand):
    help = (
        "Prints the GitHub release title or notes of a version, built from releases.yaml "
        "(English by default, the standard for GitHub releases)."
    )

    def add_arguments(self, parser):
        parser.add_argument("version", metavar="version", help="Version, e.g. 0.14.0.")
        parser.add_argument(
            "--language",
            dest="language",
            default="en",
            choices=[c for c, _n in settings.LANGUAGES],
        )
        parser.add_argument(
            "--title", dest="title", action="store_true", help="Print only the title."
        )

    def handle(self, *args, version, language, title, **options):
        release = next((r for r in releases.all_releases() if r.version == version), None)
        if release is None:
            raise CommandError(f"Version {version} is not in releases.yaml.")
        with translation.override(language):
            if title:
                name = f"{release.version} – {release.title}" if release.title else release.version
                self.stdout.write(name)
                return
            for item in release.items:
                # Dependabot items say so; on GitHub, "#6" links to the pull request.
                source = f" ({item.source_name}, #{item.pr})" if item.source else ""
                self.stdout.write(
                    f"- **{item.kind_name} · {item.module_name}:** {item.text}{source}"
                )
