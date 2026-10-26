import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Creates the superuser from DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_PASSWORD and "
        "DJANGO_ADMIN_EMAIL. Does nothing if the user already exists."
    )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        senha = os.environ.get("DJANGO_ADMIN_PASSWORD")
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "")

        if not senha:
            raise CommandError("Defina DJANGO_ADMIN_PASSWORD no .env antes de criar o admin.")

        Usuario = get_user_model()
        if Usuario.objects.filter(username=username).exists():
            self.stdout.write(f"O usuário '{username}' já existe. Nada foi alterado.")
            return

        Usuario.objects.create_superuser(username=username, email=email, password=senha)
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{username}' criado."))
