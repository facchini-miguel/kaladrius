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
        parser.add_argument("--fail-if-exists", dest="falhar_se_existir", action="store_true")

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "")

        if not password:
            raise CommandError("Defina DJANGO_ADMIN_PASSWORD no .env antes de criar o admin.")

        Usuario = get_user_model()
        if Usuario.objects.filter(username=username).exists():
            if options["falhar_se_existir"]:
                raise CommandError(f"O usuário '{username}' já existe.", returncode=3)
            self.stdout.write(f"O usuário '{username}' já existe. Nada foi alterado.")
            return

        try:
            validate_password(password, Usuario(username=username, email=email))
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        Usuario.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{username}' criado."))
