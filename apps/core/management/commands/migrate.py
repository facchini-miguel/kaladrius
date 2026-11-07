"""Django's migrate, between renaming the apps' labels in the database to the code's (decision 194)
and converting the stored choice values to the code's (decision 197).

Apps override Django's own commands, so every `migrate` (the container's start, the tests, the
Linux package, the demo's reset) runs `sync_labels` first and, when it brings the database to
the code's latest state, `sync_values` last: the old migrations run on the values of their time.
"""

from django.core.management.commands.migrate import Command as DjangoMigrate

from apps.core.labels import sync_labels
from apps.core.values import sync_values


class Command(DjangoMigrate):
    def handle(self, *args, **options):
        for old, new, migrations, content_types in sync_labels(options["database"]):
            self.stdout.write(
                f"App label {old} -> {new}: {migrations} migrations, {content_types} content types."
            )
        result = super().handle(*args, **options)
        whole = not (options["app_label"] or options["migration_name"])
        if whole and not (options["plan"] or options["check_unapplied"] or options["prune"]):
            for field, rows in sync_values(options["database"]):
                self.stdout.write(f"Stored values of {field}: {rows} rows converted.")
        return result
