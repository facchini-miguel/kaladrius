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
            dest="create_practitioner",
            action="store_true",
            help="Create the practitioner when no one has that name (an empty schedule).",
        )
        parser.add_argument("--front-desk-password", dest="front_desk_password", required=True)
        parser.add_argument("--practitioner-password", dest="practitioner_password", required=True)
        # Optional (decision 089); as demo logins, they only look at the team and settings.
        parser.add_argument(
            "--finance-password", dest="finance_password", help="Also create demo.financeiro."
        )
        parser.add_argument(
            "--admin-password",
            dest="admin_password",
            help="Also create demo.admin (clinic administrator).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        seed = os.environ.get("DJANGO_SEED_PASSWORD")
        passwords = (options["front_desk_password"], options["practitioner_password"])
        extras = [
            (FINANCE, "Financeiro", options.get("finance_password"), Role.FINANCE),
            (ADMIN, "Administrador", options.get("admin_password"), Role.ADMIN),
        ]
        extras = [extra for extra in extras if extra[2]]
        if seed and seed in (*passwords, *(extra[2] for extra in extras)):
            # The seed users (admin.sorriso included) share that password.
            raise CommandError("Não use a senha de DJANGO_SEED_PASSWORD nas contas públicas.")
        try:
            clinic = Clinic.objects.get(name=options["clinic"])
        except Clinic.DoesNotExist as error:
            raise CommandError(f"Clínica não encontrada: {options['clinic']}") from error

        reception = self._account(FRONT_DESK, "Recepção", passwords[0], clinic, Role.FRONT_DESK)
        practitioner = self._account(
            PRACTITIONER, "Profissional", passwords[1], clinic, Role.PRACTITIONER
        )
        others = [
            self._account(u, name, password, clinic, role) for u, name, password, role in extras
        ]
        with use_clinic(clinic):
            record = Practitioner.objects.filter(name=options["practitioner"]).first()
            if record is None:
                if not options["create_practitioner"]:
                    raise CommandError(
                        f"Profissional não encontrado: {options['practitioner']} "
                        "(use --create-practitioner para criar)"
                    )
                record = Practitioner.objects.create(name=options["practitioner"])
            if record.user_id not in (None, practitioner.pk):
                raise CommandError(
                    f"{record.name} já tem outro usuário de acesso; escolha outro profissional."
                )
            record.user = practitioner
            record.save(update_fields=["user"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Contas prontas: {reception.username} (recepção), {practitioner.username} "
                f"(profissional, agenda de {record.name})"
                + "".join(f", {account.username}" for account in others)
                + "."
            )
        )

    def _account(self, username, name, password, clinic, role):
        User = get_user_model()
        user, _created = User.objects.get_or_create(username=username)
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
