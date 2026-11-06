import datetime
import json
import re

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import NoCurrentClinic, use_clinic
from apps.core.models import Role
from apps.finance.models import Payment
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule import services
from apps.schedule.forms import AppointmentForm
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# A Monday well in the future, so tests never depend on today's date.
SEGUNDA = datetime.date(2031, 3, 3)


@pytest.fixture
def cenario(clinica_a, criar_profissional, criar_usuario, cliente_de):
    """Clinic A with two practitioners, a type, a patient and a front desk user."""
    with use_clinic(clinica_a):
        kind = AppointmentType.objects.get(name="Cirurgia")
        patient = Patient.objects.create(name="Maria Paciente")
    return {
        "clinic": clinica_a,
        "ana": criar_profissional(clinica_a, "Dra. Ana"),
        "bruno": criar_profissional(clinica_a, "Dr. Bruno"),
        "kind": kind,
        "patient": patient,
        "cliente": cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK)),
    }


def data(cenario, **extra):
    return {
        "practitioner": cenario["ana"].pk,
        "kind": cenario["kind"].pk,
        "patient": cenario["patient"].pk,
        "description": "",
        "date": SEGUNDA.isoformat(),
        "start_time": "09:00",
        "end_time": "10:00",
        "repeticoes": 1,
        **extra,
    }


def agendar(cenario, **extra):
    return cenario["cliente"].post(reverse("schedule:new"), data(cenario, **extra))


def agendamentos(cenario):
    with use_clinic(cenario["clinic"]):
        return list(Appointment.objects.order_by("start"))


def erros(response):
    form = response.context["form"]
    return " ".join(str(e) for results in form.errors.values() for e in results)


# --- Creating ----------------------------------------------------------------------


def test_creates_appointment_and_notifies_screen(cenario):
    response = agendar(cenario)
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "agendaAtualizada": {"mensagem": "Agendamento criado."}
    }
    [appointment] = agendamentos(cenario)
    assert appointment.patient == cenario["patient"]
    assert appointment.created_by.username == "recepcao"
    assert appointment.series is None


def test_weekly_repeat_creates_the_series(cenario):
    assert agendar(cenario, repeticoes=4).status_code == 204
    criados = agendamentos(cenario)
    assert len(criados) == 4
    assert len({a.series for a in criados}) == 1 and criados[0].series is not None
    datas = [a.start.date() for a in criados]
    assert datas == [SEGUNDA + datetime.timedelta(weeks=n) for n in range(4)]


def test_without_patient_requires_description(cenario):
    response = agendar(cenario, patient="", description="")
    assert "Informe o paciente ou uma descrição" in erros(response)
    assert agendar(cenario, patient="", description="Reunião de equipe").status_code == 204
    assert agendamentos(cenario)[0].title == "Reunião de equipe"


# --- Time rules --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("09:15", "10:00", "de 30 em 30 minutos"),
        ("09:00", "09:00", "O fim deve ser depois do início"),
        ("10:00", "09:00", "O fim deve ser depois do início"),
        ("06:00", "07:00", "Fora do horário de atendimento"),
        ("19:30", "20:30", "Fora do horário de atendimento"),
    ],
)
def test_time_rules(cenario, start, end, message):
    response = agendar(cenario, start_time=start, end_time=end)
    assert response.status_code == 200
    assert message in erros(response)
    assert agendamentos(cenario) == []


def test_interval_set_by_the_clinic(cenario):
    clinic = cenario["clinic"]
    clinic.schedule_interval = 15
    clinic.save()
    assert agendar(cenario, start_time="09:15", end_time="09:45").status_code == 204


# --- Conflicts ---------------------------------------------------------------------


def test_conflict_with_same_practitioner(cenario):
    agendar(cenario)
    response = agendar(cenario, start_time="09:30", end_time="10:30")
    assert response.status_code == 200
    assert "Conflito de horário" in erros(response)
    assert "Maria Paciente" in erros(response)
    assert len(agendamentos(cenario)) == 1


def test_adjacent_slots_and_other_practitioner_do_not_conflict(cenario):
    agendar(cenario)
    assert agendar(cenario, start_time="10:00", end_time="10:30").status_code == 204
    assert agendar(cenario, start_time="08:30", end_time="09:00").status_code == 204
    assert agendar(cenario, practitioner=cenario["bruno"].pk).status_code == 204
    assert len(agendamentos(cenario)) == 4


def test_repeat_with_conflict_saves_none(cenario):
    terceira_semana = SEGUNDA + datetime.timedelta(weeks=2)
    agendar(cenario, date=terceira_semana.isoformat())
    response = agendar(cenario, repeticoes=4)
    assert response.status_code == 200
    assert terceira_semana.strftime("%d/%m") in erros(response)
    assert "Nada foi gravado" in erros(response)
    assert len(agendamentos(cenario)) == 1


def test_database_prevents_overlap(cenario):
    """Even bypassing the form (e.g. two simultaneous requests), the database refuses."""
    with use_clinic(cenario["clinic"]):
        intervalos = services.occurrences(SEGUNDA, datetime.time(9), datetime.time(10))
        modelo = Appointment(
            practitioner=cenario["ana"], kind=cenario["kind"], description="Primeiro"
        )
        services.create(modelo, intervalos, None)
        sobreposto = services.occurrences(SEGUNDA, datetime.time(9, 30), datetime.time(10, 30))
        with pytest.raises(IntegrityError), transaction.atomic():
            services.create(modelo, sobreposto, None)


# --- Editing and deleting ----------------------------------------------------------


def test_editing_moves_time_without_conflicting_with_itself(cenario):
    agendar(cenario)
    [appointment] = agendamentos(cenario)
    url = reverse("schedule:edit", args=[appointment.pk])
    formulario = cenario["cliente"].get(url)
    assert formulario.context["form"].initial["start_time"] == datetime.time(9)
    assert "repeticoes" not in formulario.context["form"].fields
    response = cenario["cliente"].post(url, data(cenario, start_time="09:30", end_time="10:30"))
    assert response.status_code == 204
    appointment.refresh_from_db()
    assert appointment.start.astimezone().time() == datetime.time(9, 30)


def test_cancelled_slot_takes_another_patient_keeping_who_cancelled(cenario):
    """Round 2: the cancelled appointment covers the freed slot on the calendar, and changing
    its patient overwrote the record of who cancelled."""
    agendar(cenario)
    [appointment] = agendamentos(cenario)
    cliente = cenario["cliente"]
    cliente.post(reverse("schedule:status", args=[appointment.pk]), {"status": "desmarcou"})
    janela = cliente.get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    assert "Agendar outro paciente neste horário" in janela
    assert (
        f"{reverse('schedule:new')}?practitioner={cenario['ana'].pk}&amp;date={SEGUNDA}" in janela
    )
    with use_clinic(cenario["clinic"]):
        other = Patient.objects.create(name="Outro Paciente")
    troca = cliente.post(
        reverse("schedule:edit", args=[appointment.pk]), data(cenario, patient=other.pk)
    )
    assert "patient" in troca.context["form"].errors
    new_appointment = cliente.post(reverse("schedule:new"), data(cenario, patient=other.pk))
    assert new_appointment.status_code == 204
    with use_clinic(cenario["clinic"]):
        nomes = sorted((a.patient.name, a.status) for a in Appointment.objects.all())
    assert nomes == [("Maria Paciente", "desmarcou"), ("Outro Paciente", "agendado")]


def test_delete_one_or_the_series_from_then_on(cenario, criar_usuario, cliente_de):
    agendar(cenario, repeticoes=4)
    criados = agendamentos(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinic"], Role.ADMIN))

    admin.post(reverse("schedule:delete", args=[criados[0].pk]), {"escopo": "este"})
    assert len(agendamentos(cenario)) == 3

    page = admin.get(reverse("schedule:delete", args=[criados[1].pk])).content.decode()
    assert "os próximos 2" in page
    response = admin.post(reverse("schedule:delete", args=[criados[1].pk]), {"escopo": "serie"})
    assert json.loads(response["HX-Trigger"])["agendaAtualizada"]["mensagem"] == (
        "3 agendamentos excluídos."
    )
    assert agendamentos(cenario) == []


def test_archived_patient_leaves_suggestions_but_stays_on_schedule(
    cenario, criar_usuario, cliente_de
):
    agendar(cenario)
    with use_clinic(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    suggestions = cenario["cliente"].get(reverse("patients:suggestions"), {"q": "maria"})
    assert "Maria Paciente" not in suggestions.content.decode()
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    events = cenario["cliente"].get(
        reverse("schedule:events"), {**periodo, "practitioner": cenario["ana"].pk}
    )
    assert [e["title"] for e in events.json()] == ["Maria Paciente"]  # history kept


def test_permanent_deletion_removes_patient_from_appointments(cenario, criar_usuario, cliente_de):
    agendar(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinic"], Role.ADMIN))
    patient = cenario["patient"]
    admin.post(reverse("patients:archive", args=[patient.pk]))
    assert admin.post(reverse("patients:delete", args=[patient.pk])).status_code == 302
    [appointment] = agendamentos(cenario)
    assert appointment.patient is None
    # The slot stays taken, without the notes (they may hold personal data).
    assert appointment.description == f"Paciente excluído (código {patient.pk})"
    with use_clinic(cenario["clinic"]):
        assert not Patient.objects.filter(pk=patient.pk).exists()


# --- Calendar feeds ----------------------------------------------------------------


def test_period_events_in_json(cenario):
    agendar(cenario)
    agendar(cenario, date=(SEGUNDA + datetime.timedelta(weeks=1)).isoformat())
    response = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "practitioner": cenario["ana"].pk,
            "start": f"{SEGUNDA}T00:00:00-03:00",
            "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00-03:00",
        },
    )
    [evento] = response.json()
    assert evento["title"] == "Maria Paciente"
    assert evento["start"].startswith(f"{SEGUNDA}T09:00:00")
    assert evento["backgroundColor"] == "#f7a5a5"
    assert evento["extendedProps"]["kind"] == "Cirurgia"


def test_events_with_invalid_parameters(cenario):
    url = reverse("schedule:events")
    assert cenario["cliente"].get(url, {"practitioner": "x"}).status_code == 400
    longo = {"practitioner": 1, "start": "2031-01-01", "end": "2031-12-31"}
    assert cenario["cliente"].get(url, longo).status_code == 400


def test_birthdays_in_the_period(cenario):
    with use_clinic(cenario["clinic"]):
        Patient.objects.create(name="Aniversariante", birth_date=datetime.date(1990, 3, 5))
        Patient.objects.create(name="Inativo", birth_date=datetime.date(1990, 3, 5), active=False)
    response = cenario["cliente"].get(
        reverse("schedule:birthdays"),
        {"start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00"},
    )
    assert response.json() == {"2031-03-05": 1}
    results = cenario["cliente"].get(reverse("schedule:birthdays_today"), {"date": "2031-03-05"})
    assert "Aniversariante" in results.content.decode()
    assert "completa 41 anos" in results.content.decode()


def test_calendar_opens_on_chosen_practitioner(cenario):
    page = cenario["cliente"].get(
        reverse("schedule:calendar"), {"practitioner": cenario["bruno"].pk}
    )
    assert page.context["practitioner"] == cenario["bruno"]
    config = page.context["configuracao"]
    assert config["intervalo"] == 30 and config["start"] == "07:30:00"
    assert config["pode"] == {"criar": True, "alterar": True}
    # The choice is remembered for the next visit.
    assert (
        cenario["cliente"].get(reverse("schedule:calendar")).context["practitioner"]
        == cenario["bruno"]
    )


# --- Isolation and permissions -----------------------------------------------------


def test_schedule_of_another_clinic_is_invisible(cenario, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with use_clinic(clinica_b):
        tipo_b = AppointmentType.objects.get(name="Cirurgia")
        paciente_b = Patient.objects.create(name="Paciente B")
        [agendamento_b] = services.create(
            Appointment(practitioner=de_b, kind=tipo_b, patient=paciente_b),
            services.occurrences(SEGUNDA, datetime.time(9), datetime.time(10)),
            None,
        )
    cliente = cenario["cliente"]
    events = cliente.get(
        reverse("schedule:events"),
        {"practitioner": de_b.pk, "start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA}T23:00:00"},
    ).json()
    assert events == []
    assert cliente.get(reverse("schedule:edit", args=[agendamento_b.pk])).status_code == 404
    # Ids from another clinic are not accepted in the form either.
    response = agendar(cenario, practitioner=de_b.pk, kind=tipo_b.pk, patient=paciente_b.pk)
    assert set(response.context["form"].errors) >= {"practitioner", "kind", "patient"}


def cliente_da_dra_ana(cenario, criar_usuario, cliente_de):
    """A practitioner user linked to Dra. Ana's record."""
    user = criar_usuario("dra", cenario["clinic"], Role.PRACTITIONER)
    with use_clinic(cenario["clinic"]):
        Practitioner.objects.filter(pk=cenario["ana"].pk).update(user=user)
    return cliente_de(user)


def test_practitioner_books_but_does_not_delete(cenario, criar_usuario, cliente_de):
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert cliente.post(reverse("schedule:new"), data(cenario)).status_code == 204
    [appointment] = agendamentos(cenario)
    assert cliente.post(reverse("schedule:delete", args=[appointment.pk])).status_code == 403
    formulario = cliente.get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    assert "Excluir" not in formulario


def test_practitioner_sees_only_own_schedule(cenario, criar_usuario, cliente_de):
    assert agendar(cenario, practitioner=cenario["bruno"].pk).status_code == 204
    [do_bruno] = agendamentos(cenario)
    # The front desk sees every practitioner (checked first: the test client is shared).
    response = cenario["cliente"].get(reverse("schedule:calendar"))
    assert len(response.context["profissionais"]) == 2
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)

    response = cliente.get(reverse("schedule:calendar"), {"practitioner": cenario["bruno"].pk})
    assert [p.name for p in response.context["profissionais"]] == ["Dra. Ana"]
    assert response.context["practitioner"] == cenario["ana"]
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    events = cliente.get(
        reverse("schedule:events"), {**periodo, "practitioner": cenario["bruno"].pk}
    )
    assert events.json() == []
    assert cliente.get(reverse("schedule:edit", args=[do_bruno.pk])).status_code == 404

    response = cliente.post(
        reverse("schedule:new"),
        data(cenario, practitioner=cenario["bruno"].pk, start_time="11:00", end_time="12:00"),
    )
    assert response.status_code == 200
    assert "practitioner" in response.context["form"].errors


def test_practitioner_without_linked_profile_sees_no_schedule(cenario, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("sem_cadastro", cenario["clinic"], Role.PRACTITIONER))
    response = cliente.get(reverse("schedule:calendar"))
    assert response.context["profissionais"] == []
    assert "não está ligado a um cadastro de profissional" in response.content.decode()


def test_patient_suggestions_only_from_the_clinic(cenario, clinica_b):
    with use_clinic(clinica_b):
        Patient.objects.create(name="Maria de Outra Clínica")
    content = (
        cenario["cliente"].get(reverse("patients:suggestions"), {"q": "maria"}).content.decode()
    )
    assert "Maria Paciente" in content
    assert "Outra Clínica" not in content


def test_clinic_filter_is_decided_at_run_time(clinica_a):
    # Building a queryset (e.g. form field choices at import time) must not fail...
    consulta = Appointment.objects.filter(description="x")
    assert AppointmentForm.base_fields["practitioner"].queryset is not None
    # ...but running it without a current clinic must.
    with pytest.raises(NoCurrentClinic):
        list(consulta)
    with use_clinic(clinica_a):
        assert list(consulta) == []


def test_period_with_and_without_time_zone_mixed(cenario):
    response = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "start": "2031-03-03T00:00:00",
            "end": "2031-03-10T00:00:00-03:00",
            "practitioner": cenario["ana"].pk,
        },
    )
    assert response.status_code == 200


# --- Patient record history --------------------------------------------------------


def test_record_shows_upcoming_and_past(cenario, criar_usuario, cliente_de):
    now = timezone.localtime()
    passado = now.date() - datetime.timedelta(days=7)
    with use_clinic(cenario["clinic"]):
        Appointment.objects.create(
            practitioner=cenario["ana"],
            kind=cenario["kind"],
            patient=cenario["patient"],
            start=services.timestamp(passado, datetime.time(9)),
            end=services.timestamp(passado, datetime.time(10)),
        )
    agendar(cenario)  # 2031, Dra. Ana
    agendar(cenario, practitioner=cenario["bruno"].pk, start_time="11:00", end_time="12:00")
    url = reverse("patients:record", args=[cenario["patient"].pk])

    historico = cenario["cliente"].get(url).context["agendamentos"]
    assert historico["total"] == 3
    assert [a.practitioner.name for a in historico["proximos"]] == ["Dra. Ana", "Dr. Bruno"]
    assert [a.start.date() for a in historico["anteriores"]] == [passado]

    # Practitioners see only their own appointments in the record too.
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    response = cliente.get(url)
    historico = response.context["agendamentos"]
    assert historico["total"] == 2
    assert {a.practitioner.name for a in historico["proximos"]} == {"Dra. Ana"}
    assert "?practitioner=" in response.content.decode()


# --- Simulated activity --------------------------------------------------------------


def test_simulate_activity_respects_taken_slots(cenario):
    # A real appointment today at 09:00 for Dra. Ana must stay untouched.
    today = timezone.localdate()
    with use_clinic(cenario["clinic"]):
        Patient.objects.create(name="Arquivado", archived=True)
        existente = Appointment.objects.create(
            practitioner=cenario["ana"],
            kind=cenario["kind"],
            start=services.timestamp(today, datetime.time(9)),
            end=services.timestamp(today, datetime.time(10)),
            description="Real",
        )
    with pytest.raises(CommandError):
        call_command("simulate_activity", clinic=cenario["clinic"].name)
    call_command("simulate_activity", clinic=cenario["clinic"].name, confirmar=True)

    with use_clinic(cenario["clinic"]):
        novos = Appointment.objects.exclude(pk=existente.pk)
        assert novos.count() > 0
        assert not novos.filter(
            practitioner=cenario["ana"], start__lt=existente.end, end__gt=existente.start
        ).exists()
        assert not novos.filter(patient__archived=True).exists()
        assert novos.filter(kind__name="Ocupado").count() == 0
        assert Recall.objects.count() == 80
        assert not Recall.objects.filter(patient__archived=True).exists()
        # Cheques are not used anymore, not even in made-up data.
        assert Payment.objects.exists()
        assert not Payment.objects.filter(method=Payment.Method.CHEQUE).exists()


def test_simulate_only_recalls(cenario):
    call_command(
        "simulate_activity",
        clinic=cenario["clinic"].name,
        sem_agenda=True,
        rechamadas=5,
        confirmar=True,
    )
    with use_clinic(cenario["clinic"]):
        assert not Appointment.objects.exists()
        assert Recall.objects.count() == 5


# --- Came / missed / cancelled (0.24.0) ---------------------------------------------------


def agendamento_em(cenario, day, hour=9, patient=True, practitioner="ana"):
    with use_clinic(cenario["clinic"]):
        return Appointment.objects.create(
            practitioner=cenario[practitioner],
            kind=cenario["kind"],
            patient=cenario["patient"] if patient else None,
            description="" if patient else "Bloqueado",
            start=services.timestamp(day, datetime.time(hour)),
            end=services.timestamp(day, datetime.time(hour + 1)),
        )


def mark(cenario, appointment, status, htmx=True, cliente=None):
    cabecalhos = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return (cliente or cenario["cliente"]).post(
        reverse("schedule:status", args=[appointment.pk]), {"status": status}, **cabecalhos
    )


def situacao_de(cenario, appointment):
    with use_clinic(cenario["clinic"]):
        return Appointment.objects.get(pk=appointment.pk).status


def test_marks_attendance_and_no_show_from_the_day(cenario):
    today = timezone.localdate()
    appointment = agendamento_em(cenario, today)
    response = mark(cenario, appointment, "compareceu")
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "agendaAtualizada": {"mensagem": "Maria Paciente compareceu."}
    }
    assert situacao_de(cenario, appointment) == "compareceu"
    assert mark(cenario, appointment, "agendado").status_code == 204
    assert situacao_de(cenario, appointment) == "agendado"

    # The appointment window shows the buttons; a future one only offers "cancelled".
    janela = cenario["cliente"].get(reverse("schedule:edit", args=[appointment.pk]))
    assert "Compareceu" in janela.content.decode()
    futuro = agendamento_em(cenario, SEGUNDA)
    janela = cenario["cliente"].get(reverse("schedule:edit", args=[futuro.pk])).content.decode()
    assert '"status": "faltou"' not in janela and '"status": "desmarcou"' in janela
    response = mark(cenario, futuro, "faltou")
    assert response.status_code == 200
    assert "a partir do dia do atendimento" in response.context["erro_situacao"]
    assert situacao_de(cenario, futuro) == "agendado"


def test_status_button_sends_what_the_view_reads(cenario):
    """The window's buttons post their hx-vals: pressing one must change the status."""
    appointment = agendamento_em(cenario, timezone.localdate())
    janela = (
        cenario["cliente"].get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    )
    botao = re.search(r'hx-post="([^"]+)" hx-vals=\'([^\']+)\'[^>]*>✓', janela)
    assert botao, "no Compareceu button in the window"
    response = cenario["cliente"].post(botao[1], json.loads(botao[2]), HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert situacao_de(cenario, appointment) == "compareceu"


def test_invalid_status_and_slot_without_patient_are_refused(cenario):
    today = timezone.localdate()
    bloqueio = agendamento_em(cenario, today, patient=False)
    response = mark(cenario, bloqueio, "compareceu", htmx=False)
    assert response.status_code == 302 and response.url == reverse("home")
    assert situacao_de(cenario, bloqueio) == "agendado"
    appointment = agendamento_em(cenario, today, hour=11)
    mark(cenario, appointment, "chegou")
    assert situacao_de(cenario, appointment) == "agendado"
    assert (
        cenario["cliente"].get(reverse("schedule:status", args=[appointment.pk])).status_code == 405
    )


def test_cancelled_frees_the_slot(cenario):
    agendar(cenario)
    [first] = agendamentos(cenario)
    assert mark(cenario, first, "desmarcou").status_code == 204
    # The slot is free again for another patient, also for the database constraint.
    assert agendar(cenario).status_code == 204
    assert len(agendamentos(cenario)) == 2
    # Undoing the cancellation would double-book: refused.
    response = mark(cenario, first, "agendado")
    assert "já foi ocupado" in response.context["erro_situacao"]
    assert situacao_de(cenario, first) == "desmarcou"
    # Editing the cancelled one does not conflict with the new one either.
    response = cenario["cliente"].post(
        reverse("schedule:edit", args=[first.pk]), data(cenario, description="Remarcar")
    )
    assert response.status_code == 204


def test_rescheduling_to_future_or_removing_patient_clears_attendance(cenario):
    today = timezone.localdate()
    appointment = agendamento_em(cenario, today)
    mark(cenario, appointment, "faltou")
    response = cenario["cliente"].post(
        reverse("schedule:edit", args=[appointment.pk]), data(cenario)
    )
    assert response.status_code == 204
    assert situacao_de(cenario, appointment) == "agendado"

    other = agendamento_em(cenario, today, hour=11)
    mark(cenario, other, "compareceu")
    sem_paciente = data(
        cenario,
        patient="",
        description="Bloqueado",
        date=today.isoformat(),
        start_time="11:00",
        end_time="12:00",
    )
    cenario["cliente"].post(reverse("schedule:edit", args=[other.pk]), sem_paciente)
    assert situacao_de(cenario, other) == "agendado"


def test_practitioner_marks_only_own_schedule(cenario, criar_usuario, cliente_de):
    today = timezone.localdate()
    do_bruno = agendamento_em(cenario, today, practitioner="bruno")
    da_ana = agendamento_em(cenario, today)
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert mark(cenario, do_bruno, "compareceu", cliente=cliente).status_code == 404
    assert mark(cenario, da_ana, "compareceu", cliente=cliente).status_code == 204


def test_events_carry_the_status(cenario):
    appointment = agendamento_em(cenario, timezone.localdate())
    mark(cenario, appointment, "faltou")
    today = timezone.localdate()
    response = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "practitioner": cenario["ana"].pk,
            "start": today.isoformat(),
            "end": (today + datetime.timedelta(days=1)).isoformat(),
        },
    )
    [evento] = response.json()
    assert evento["classNames"] == ["status-faltou"]
    assert evento["extendedProps"]["status_name"] == "Faltou"


def test_default_types_show_in_user_language(cenario):
    """The default types are saved in Portuguese and shown translated; a type the clinic
    typed itself is shown as saved."""
    cliente = cenario["cliente"]
    with use_clinic(cenario["clinic"]):
        AppointmentType.objects.create(name="Clareamento a laser", color="#ffffff")

    cliente.post(reverse("change_language"), {"language": "en"})
    legenda = cliente.get(reverse("schedule:calendar")).content.decode()
    assert ">Surgery<" in legenda and ">Orthodontics<" in legenda
    assert ">Cirurgia<" not in legenda
    assert ">Clareamento a laser<" in legenda
    assert ">Surgery</option>" in cliente.get(reverse("schedule:new")).content.decode()

    cliente.post(reverse("change_language"), {"language": "es"})
    assert ">Cirugía<" in cliente.get(reverse("schedule:calendar")).content.decode()
    with use_clinic(cenario["clinic"]):
        assert AppointmentType.objects.filter(name="Cirurgia").exists()  # data untouched
