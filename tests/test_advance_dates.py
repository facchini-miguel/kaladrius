import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.agenda import servicos as agenda
from apps.agenda.models import Agendamento, TipoAtendimento
from apps.core.isolamento import usar_clinica
from apps.pacientes.models import Paciente
from apps.rechamadas.models import Rechamada


@pytest.fixture
def cenario(clinica_a, criar_profissional):
    hoje = timezone.localdate()
    ana = criar_profissional(clinica_a, "Dra. Ana")
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(
            nome="Maria Paciente", data_nascimento=datetime.date(1980, 5, 17)
        )
        tipo = TipoAtendimento.objects.first()
        # Same time, one week apart: moving one week at a time row by row would overlap.
        semana = [
            Agendamento.objects.create(
                profissional=ana,
                tipo=tipo,
                paciente=paciente,
                inicio=agenda.momento(hoje - datetime.timedelta(days=d), datetime.time(9)),
                fim=agenda.momento(hoje - datetime.timedelta(days=d), datetime.time(10)),
            )
            for d in (21, 14)
        ]
        rechamada = Rechamada.objects.create(
            paciente=paciente, data=hoje - datetime.timedelta(days=20), descricao="Limpeza"
        )
    return {"clinica": clinica_a, "paciente": paciente, "agenda": semana, "rechamada": rechamada}


def test_so_no_servidor_de_demonstracao(cenario, settings):
    settings.DEMONSTRACAO = False
    with pytest.raises(CommandError, match="DJANGO_DEMONSTRACAO"):
        call_command("avancar_datas", desde="2026-01-01", confirmar=True)
    settings.DEMONSTRACAO = True
    with pytest.raises(CommandError, match="--confirmar"):
        call_command("avancar_datas", desde="2026-01-01")


def test_avanca_semanas_inteiras_e_nao_mexe_no_nascimento(cenario, settings):
    settings.DEMONSTRACAO = True
    hoje = timezone.localdate()
    antes = {a.pk: (a.inicio, a.fim) for a in cenario["agenda"]}
    # 17 days ago: two whole weeks, so each appointment keeps its weekday.
    call_command("avancar_datas", desde=str(hoje - datetime.timedelta(days=17)), confirmar=True)
    with usar_clinica(cenario["clinica"]):
        for agendamento in Agendamento.objects.all():
            inicio, fim = antes[agendamento.pk]
            assert agendamento.inicio - inicio == datetime.timedelta(days=14)
            assert agendamento.fim - fim == datetime.timedelta(days=14)
            assert agendamento.inicio.weekday() == inicio.weekday()
        assert Rechamada.objects.get().data == hoje - datetime.timedelta(days=6)
        assert Paciente.objects.get().data_nascimento == datetime.date(1980, 5, 17)
        # The no-double-booking constraint is back.
        with pytest.raises(Exception, match="agendamento_sem_sobreposicao"):
            primeiro = Agendamento.objects.first()
            Agendamento.objects.create(
                profissional=primeiro.profissional,
                tipo=primeiro.tipo,
                inicio=primeiro.inicio,
                fim=primeiro.fim,
            )


def test_menos_de_uma_semana_nao_muda_nada(cenario, settings):
    settings.DEMONSTRACAO = True
    hoje = timezone.localdate()
    call_command("avancar_datas", desde=str(hoje - datetime.timedelta(days=6)), confirmar=True)
    with usar_clinica(cenario["clinica"]):
        assert Rechamada.objects.get().data == hoje - datetime.timedelta(days=20)
