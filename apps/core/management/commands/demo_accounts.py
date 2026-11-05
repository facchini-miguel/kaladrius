import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Membership, Role
from apps.practitioners.models import Practitioner

FRONT_DESK = "demo.recepcao"
PRACTITIONER = "demo.profissional"
FINANCE = "demo.financeiro"
ADMIN = "demo.admin"


class Command(BaseCommand):
    help = (
        "Creates (or resets) the public demo logins: demo.recepcao (front desk) and "
        "demo.profissional (practitioner, linked to a practitioner without a login; "
        "--create-practitioner creates it when missing). Their passwords are meant to be "
        "published, so they cannot change them nor upload attachments (decision 085). "
        "Never reuse DJANGO_SEED_PASSWORD."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinic", dest="clinic", required=True, help="Clinic name.")
        parser.add_argument(
            "--practitioner",
            dest="practitioner",
            required=True,
            help="Practitioner the demo practitioner login uses.",
        )
        parser.add_argument(
            "--create-practitioner",
            dest="criar_profissional",
            action="store_true",
            help="Create the practitioner when no one has that name (an empty schedule).",
        )
        parser.add_argument("--front-desk-password", dest="senha_recepcao", required=True)
        parser.add_argument("--practitioner-password", dest="senha_profissional", required=True)
        # Optional (decision 089); as demo logins, they only look at the team and settings.
        parser.add_argument(
            "--finance-password", dest="senha_financeiro", help="Also create demo.financeiro."
        )
        parser.add_argument(
            "--admin-password",
            dest="senha_admin",
            help="Also create demo.admin (clinic administrator).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        semente = os.environ.get("DJANGO_SEED_PASSWORD")
        senhas = (options["senha_recepcao"], options["senha_profissional"])
        extras = [
            (FINANCE, "Financeiro", options.get("senha_financeiro"), Role.FINANCE),
            (ADMIN, "Administrador", options.get("senha_admin"), Role.ADMIN),
        ]
        extras = [extra for extra in extras if extra[2]]
        if semente and semente in (*senhas, *(extra[2] for extra in extras)):
            # The seed users (admin.sorriso included) share that password.
            raise CommandError("Não use a senha de DJANGO_SEED_PASSWORD nas contas públicas.")
        try:
            clinic = Clinic.objects.get(name=options["clinic"])
        except Clinic.DoesNotExist as error:
            raise CommandError(f"Clínica não encontrada: {options['clinic']}") from error

        reception = self._account(FRONT_DESK, "Recepção", senhas[0], clinic, Role.FRONT_DESK)
        practitioner = self._account(
            PRACTITIONER, "Profissional", senhas[1], clinic, Role.PRACTITIONER
        )
        outras = [
            self._account(u, name, password, clinic, role) for u, name, password, role in extras
        ]
        with use_clinic(clinic):
            cadastro = Practitioner.objects.filter(name=options["practitioner"]).first()
            if cadastro is None:
                if not options["criar_profissional"]:
                    raise CommandError(
                        f"Profissional não encontrado: {options['practitioner']} "
                        "(use --create-practitioner para criar)"
                    )
                cadastro = Practitioner.objects.create(name=options["practitioner"])
            if cadastro.user_id not in (None, practitioner.pk):
                raise CommandError(
                    f"{cadastro.name} já tem outro usuário de acesso; escolha outro profissional."
                )
            cadastro.user = practitioner
            cadastro.save(update_fields=["user"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Contas prontas: {reception.username} (recepção), {practitioner.username} "
                f"(profissional, agenda de {cadastro.name})"
                + "".join(f", {account.username}" for account in outras)
                + "."
            )
        )

    def _account(self, username, name, password, clinic, role):
        User = get_user_model()
        user, _criado = User.objects.get_or_create(username=username)
        user.first_name = name
        user.last_name = "(demonstração)"
        user.is_active = True
        user.is_staff = user.is_superuser = False
        user.demo = True
        user.set_password(password)
        user.save()
        Membership.objects.update_or_create(
            user=user, clinic=clinic, defaults={"role": role, "active": True}
        )
        return user
