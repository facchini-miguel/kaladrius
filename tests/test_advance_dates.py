import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.patients.models import Patient
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType


@pytest.fixture
def cenario(clinica_a, criar_profissional):
    hoje = timezone.localdate()
    ana = criar_profissional(clinica_a, "Dra. Ana")
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(
            name="Maria Paciente", data_nascimento=datetime.date(1980, 5, 17)
        )
        kind = AppointmentType.objects.first()
        # Same time, one week apart: moving one week at a time row by row would overlap.
        semana = [
            Appointment.objects.create(
                practitioner=ana,
                kind=kind,
                patient=patient,
                inicio=agenda.momento(hoje - datetime.timedelta(days=d), datetime.time(9)),
                fim=agenda.momento(hoje - datetime.timedelta(days=d), datetime.time(10)),
            )
            for d in (21, 14)
        ]
        rechamada = Recall.objects.create(
            patient=patient, data=hoje - datetime.timedelta(days=20), description="Limpeza"
        )
    return {"clinic": clinica_a, "patient": patient, "agenda": semana, "rechamada": rechamada}


def test_so_no_servidor_de_demonstracao(cenario, settings):
    settings.DEMO = False
    with pytest.raises(CommandError, match="DJANGO_DEMO"):
        call_command("advance_dates", desde="2026-01-01", confirmar=True)
    settings.DEMO = True
    with pytest.raises(CommandError, match="--confirm"):
        call_command("advance_dates", desde="2026-01-01")


def test_avanca_semanas_inteiras_e_nao_mexe_no_nascimento(cenario, settings):
    settings.DEMO = True
    hoje = timezone.localdate()
    antes = {a.pk: (a.inicio, a.fim) for a in cenario["agenda"]}
    # 17 days ago: two whole weeks, so each appointment keeps its weekday.
    call_command("advance_dates", desde=str(hoje - datetime.timedelta(days=17)), confirmar=True)
    with usar_clinica(cenario["clinic"]):
        for agendamento in Appointment.objects.all():
            inicio, fim = antes[agendamento.pk]
            assert agendamento.inicio - inicio == datetime.timedelta(days=14)
            assert agendamento.fim - fim == datetime.timedelta(days=14)
            assert agendamento.inicio.weekday() == inicio.weekday()
        assert Recall.objects.get().data == hoje - datetime.timedelta(days=6)
        assert Patient.objects.get().data_nascimento == datetime.date(1980, 5, 17)
        # The no-double-booking constraint is back.
        with pytest.raises(Exception, match="agendamento_sem_sobreposicao"):
            primeiro = Appointment.objects.first()
            Appointment.objects.create(
                practitioner=primeiro.practitioner,
                kind=primeiro.kind,
                inicio=primeiro.inicio,
                fim=primeiro.fim,
            )


def test_menos_de_uma_semana_nao_muda_nada(cenario, settings):
    settings.DEMO = True
    hoje = timezone.localdate()
    call_command("advance_dates", desde=str(hoje - datetime.timedelta(days=6)), confirmar=True)
    with usar_clinica(cenario["clinic"]):
        assert Recall.objects.get().data == hoje - datetime.timedelta(days=20)
