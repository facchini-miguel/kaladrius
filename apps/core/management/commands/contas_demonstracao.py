import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica, Papel, Vinculo
from apps.profissionais.models import Profissional

RECEPCAO = "demo.recepcao"
PROFISSIONAL = "demo.profissional"


class Command(BaseCommand):
    help = (
        "Creates (or resets) the public demo logins: demo.recepcao (front desk) and "
        "demo.profissional (practitioner, linked to a practitioner without a login; "
        "--criar-profissional creates it when missing). Their passwords are meant to be "
        "published, so they cannot change them nor upload attachments (decision 085). "
        "Never reuse DJANGO_SEED_PASSWORD."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinica", required=True, help="Clinic name.")
        parser.add_argument(
            "--profissional", required=True, help="Practitioner the demo practitioner login uses."
        )
        parser.add_argument(
            "--criar-profissional",
            action="store_true",
            help="Create the practitioner when no one has that name (an empty schedule).",
        )
        parser.add_argument("--senha-recepcao", required=True)
        parser.add_argument("--senha-profissional", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        semente = os.environ.get("DJANGO_SEED_PASSWORD")
        senhas = (options["senha_recepcao"], options["senha_profissional"])
        if semente and semente in senhas:
            # The seed users (admin.sorriso included) share that password.
            raise CommandError("Não use a senha de DJANGO_SEED_PASSWORD nas contas públicas.")
        try:
            clinica = Clinica.objects.get(nome=options["clinica"])
        except Clinica.DoesNotExist as erro:
            raise CommandError(f"Clínica não encontrada: {options['clinica']}") from erro

        recepcao = self._conta(RECEPCAO, "Recepção", senhas[0], clinica, Papel.RECEPCAO)
        profissional = self._conta(
            PROFISSIONAL, "Profissional", senhas[1], clinica, Papel.PROFISSIONAL
        )
        with usar_clinica(clinica):
            cadastro = Profissional.objects.filter(nome=options["profissional"]).first()
            if cadastro is None:
                if not options["criar_profissional"]:
                    raise CommandError(
                        f"Profissional não encontrado: {options['profissional']} "
                        "(use --criar-profissional para criar)"
                    )
                cadastro = Profissional.objects.create(nome=options["profissional"])
            if cadastro.usuario_id not in (None, profissional.pk):
                raise CommandError(
                    f"{cadastro.nome} já tem outro usuário de acesso; escolha outro profissional."
                )
            cadastro.usuario = profissional
            cadastro.save(update_fields=["usuario"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Contas prontas: {recepcao.username} (recepção) e {profissional.username} "
                f"(profissional, agenda de {cadastro.nome})."
            )
        )

    def _conta(self, username, nome, senha, clinica, papel):
        Usuario = get_user_model()
        usuario, _criado = Usuario.objects.get_or_create(username=username)
        usuario.first_name = nome
        usuario.last_name = "(demonstração)"
        usuario.is_active = True
        usuario.is_staff = usuario.is_superuser = False
        usuario.demonstracao = True
        usuario.set_password(senha)
        usuario.save()
        Vinculo.objects.update_or_create(
            usuario=usuario, clinica=clinica, defaults={"papel": papel, "ativo": True}
        )
        return usuario
