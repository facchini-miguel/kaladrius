import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica, Papel, Vinculo
from apps.profissionais.models import Profissional

# Fake data only. Names, registrations and e-mails are invented.
CLINICAS = [
    {
        "nome": "Clínica Sorriso (teste)",
        "dados": {"telefone": "(48) 3000-0001"},
        "usuarios": [
            ("admin.sorriso", "Beatriz", "Lima", Papel.ADMIN),
            ("recepcao.sorriso", "Carla", "Mendes", Papel.RECEPCAO),
            ("dra.ana", "Ana", "Souza", Papel.PROFISSIONAL),
        ],
        "profissionais": [
            ("Dra. Ana Souza", "CRO-SC 10001", "#0d6efd", "dra.ana"),
            ("Dr. Bruno Alves", "CRO-SC 10002", "#198754", None),
            ("Consultório 2", "", "#6f42c1", None),
        ],
    },
    {
        "nome": "Clínica Bem Estar (teste)",
        "dados": {"telefone": "(48) 3000-0002", "agenda_intervalo": 60},
        "usuarios": [
            ("admin.bemestar", "Eduardo", "Ramos", Papel.ADMIN),
            ("recepcao.bemestar", "Fernanda", "Dias", Papel.RECEPCAO),
            ("dr.carlos", "Carlos", "Pereira", Papel.PROFISSIONAL),
        ],
        "profissionais": [
            ("Dr. Carlos Pereira", "CRM-SC 20001", "#dc3545", "dr.carlos"),
            ("Júlia Rocha (fisioterapia)", "CREFITO-10 20002", "#fd7e14", None),
        ],
    },
]

# A front desk user that works in both clinics, to test the clinic switcher.
USUARIO_MULTICLINICA = ("recepcao.multi", "Diego", "Costa", Papel.RECEPCAO)


class Command(BaseCommand):
    help = (
        "Creates fake test data (clinics, users and practitioners). "
        "Development only: never run it in production."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcar", action="store_true", help="Run even when DJANGO_DEBUG is off."
        )

    def handle(self, *args, forcar=False, **options):
        if not settings.DEBUG and not forcar:
            raise CommandError(
                "Dados de teste só podem ser criados com DJANGO_DEBUG=1 "
                "(use --forcar para ignorar)."
            )
        senha = os.environ.get("DJANGO_SEED_PASSWORD")
        if not senha:
            raise CommandError(
                "Defina DJANGO_SEED_PASSWORD no .env antes de criar os dados de teste."
            )

        criados = []
        with transaction.atomic(), sem_isolamento():
            clinicas = []
            for dados in CLINICAS:
                clinica, _ = Clinica.objects.get_or_create(
                    nome=dados["nome"], defaults=dados["dados"]
                )
                clinicas.append(clinica)
                for username, nome, sobrenome, papel in dados["usuarios"]:
                    usuario = self._usuario(username, nome, sobrenome, senha, criados)
                    Vinculo.objects.get_or_create(
                        usuario=usuario, clinica=clinica, defaults={"papel": papel}
                    )
                for nome, registro, cor, username in dados["profissionais"]:
                    usuario = get_user_model().objects.filter(username=username).first()
                    Profissional.objects.get_or_create(
                        clinica=clinica,
                        nome=nome,
                        defaults={"registro": registro, "cor": cor, "usuario": usuario},
                    )

            username, nome, sobrenome, papel = USUARIO_MULTICLINICA
            usuario = self._usuario(username, nome, sobrenome, senha, criados)
            for clinica in clinicas:
                Vinculo.objects.get_or_create(
                    usuario=usuario, clinica=clinica, defaults={"papel": papel}
                )

        self.stdout.write(self.style.SUCCESS("Dados de teste prontos."))
        if criados:
            self.stdout.write(
                f"Usuários criados (senha em DJANGO_SEED_PASSWORD): {', '.join(criados)}"
            )
        else:
            self.stdout.write("Nenhum usuário novo: os dados de teste já existiam.")

    def _usuario(self, username, nome, sobrenome, senha, criados):
        usuario, criado = get_user_model().objects.get_or_create(
            username=username,
            defaults={
                "first_name": nome,
                "last_name": sobrenome,
                "email": f"{username}@example.com",
            },
        )
        if criado:
            usuario.set_password(senha)
            usuario.save(update_fields=["password"])
            criados.append(username)
        return usuario
