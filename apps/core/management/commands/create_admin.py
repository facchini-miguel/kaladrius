import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Creates the superuser from DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_PASSWORD and "
        "DJANGO_ADMIN_EMAIL. Does nothing if the user already exists (with --fail-if-exists, "
        "fails with exit status 3). The password must pass the system's password rules (the "
        "Linux package's installer shows the reasons and asks again)."
    )

    def add_arguments(self, parser):
        # The Linux package's installer (decision 140): the password just typed would be thrown
        # away without a word, so it tells the user instead.
        parser.add_argument("--fail-if-exists", dest="fail_if_exists", action="store_true")

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "")

        if not password:
            raise CommandError("Set DJANGO_ADMIN_PASSWORD in .env before creating the admin.")

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            if options["fail_if_exists"]:
                raise CommandError(f"User '{username}' already exists.", returncode=3)
            self.stdout.write(f"User '{username}' already exists. Nothing was changed.")
            return

        try:
            validate_password(password, User(username=username, email=email))
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
