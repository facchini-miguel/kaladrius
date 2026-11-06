"""Django's migrate, after renaming the apps' labels in the database to the code's (decision 194).

Apps override Django's own commands, so every `migrate` (the container's start, the tests, the
Linux package, the demo's reset) runs `sync_labels` first.
"""

from django.core.management.commands.migrate import Command as DjangoMigrate

from apps.core.labels import sync_labels


class Command(DjangoMigrate):
    def handle(self, *args, **options):
        for old, new, migrations, content_types in sync_labels(options["database"]):
            self.stdout.write(
                f"App label {old} -> {new}: {migrations} migrations, {content_types} content types."
            )
        return super().handle(*args, **options)
