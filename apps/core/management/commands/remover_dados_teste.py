from axes.models import AccessAttempt, AccessLog
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import registrar
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica
from apps.financeiro.models import (
    Caixa,
    Categoria,
    Comissao,
    Conta,
    ImportacaoExtrato,
    Lancamento,
    MovimentoCaixa,
    Pagamento,
    Parcela,
    TransacaoBancaria,
)
from apps.orcamentos.models import ItemOrcamento, Orcamento, Procedimento
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

from .popular_dados_teste import CLINICAS, USUARIO_MULTICLINICA


class Command(BaseCommand):
    help = (
        "Deletes the fake data created by popular_dados_teste: the '(teste)' clinics with "
        "everything in them, the test users and their audit and login records. Real "
        "clinics and users are never touched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar", action="store_true", help="Required: the deletion cannot be undone."
        )

    def handle(self, *args, confirmar=False, **options):
        if not confirmar:
            raise CommandError("Nada foi apagado: rode de novo com --confirmar.")
        nomes = [dados["nome"] for dados in CLINICAS]
        usernames = [u[0] for dados in CLINICAS for u in dados["usuarios"]]
        usernames.append(USUARIO_MULTICLINICA[0])

        with transaction.atomic(), sem_isolamento():
            clinicas = list(Clinica.objects.filter(nome__in=nomes))
            # Only users that work solely in the test clinics, never a platform account.
            usuarios = list(
                get_user_model()
                .objects.filter(username__in=usernames, is_superuser=False, is_staff=False)
                .exclude(
                    vinculos__clinica__in=Clinica.objects.exclude(pk__in=[c.pk for c in clinicas])
                )
            )
            pacientes = Paciente.objects.filter(clinica__in=clinicas).count()
            # Clinic data is protected against deleting the clinic, so it goes first.
            for modelo in (
                TransacaoBancaria,
                ImportacaoExtrato,
                ItemOrcamento,
                Orcamento,
                Procedimento,
                MovimentoCaixa,
                Caixa,
                Pagamento,
                Comissao,
                Parcela,
                Lancamento,
                Agendamento,
                Rechamada,
                Paciente,
                Profissional,
                TipoAtendimento,
                Conta,
                Categoria,
            ):
                modelo.objects.filter(clinica__in=clinicas).delete()
            # Collected now: delete() clears the instances' pk.
            ids_usuarios = [u.pk for u in usuarios]
            ids_clinicas = [c.pk for c in clinicas]
            for usuario in usuarios:
                usuario.delete()
            for clinica in clinicas:
                clinica.delete()
            # Their history, including the entries the deletion itself just wrote.
            RegistroAuditoria.objects.filter(clinica_id__in=ids_clinicas).delete()
            RegistroAuditoria.objects.filter(usuario_id__in=ids_usuarios).delete()
            RegistroAuditoria.objects.filter(
                modelo__in=["Usuário", "Clínica"],
                objeto_id__in=[str(i) for i in ids_usuarios + ids_clinicas],
            ).delete()
            nomes_usuarios = [u.username for u in usuarios]
            AccessLog.objects.filter(username__in=nomes_usuarios).delete()
            AccessAttempt.objects.filter(username__in=nomes_usuarios).delete()
            registrar(
                RegistroAuditoria.Acao.EXCLUIR,
                descricao=(
                    f"Dados de teste removidos: {len(clinicas)} clínicas, {pacientes} pacientes, "
                    f"{len(usuarios)} usuários"
                ),
            )

        self.stdout.write(self.style.SUCCESS("Dados de teste removidos."))
        self.stdout.write(f"Clínicas: {', '.join(c.nome for c in clinicas) or 'nenhuma'}")
        self.stdout.write(f"Pacientes fictícios: {pacientes}")
        self.stdout.write(f"Usuários: {', '.join(nomes_usuarios) or 'nenhum'}")
