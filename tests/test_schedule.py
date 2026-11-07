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
MONDAY = datetime.date(2031, 3, 3)


@pytest.fixture
def scenario(clinic_a, create_practitioner, create_user, client_for):
    """Clinic A with two practitioners, a type, a patient and a front desk user."""
    with use_clinic(clinic_a):
        kind = AppointmentType.objects.get(name="Cirurgia")
        patient = Patient.objects.create(name="Maria Paciente")
    return {
        "clinic": clinic_a,
        "ana": create_practitioner(clinic_a, "Dra. Ana"),
        "bruno": create_practitioner(clinic_a, "Dr. Bruno"),
        "kind": kind,
        "patient": patient,
        "client": client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK)),
    }


def data(scenario, **extra):
    return {
        "practitioner": scenario["ana"].pk,
        "kind": scenario["kind"].pk,
        "patient": scenario["patient"].pk,
        "description": "",
        "date": MONDAY.isoformat(),
        "start_time": "09:00",
        "end_time": "10:00",
        "repetitions": 1,
        **extra,
    }


def book(scenario, **extra):
    return scenario["client"].post(reverse("schedule:new"), data(scenario, **extra))


def appointment_list(scenario):
    with use_clinic(scenario["clinic"]):
        return list(Appointment.objects.order_by("start"))


def errors(response):
    form = response.context["form"]
    return " ".join(str(e) for results in form.errors.values() for e in results)


# --- Creating ----------------------------------------------------------------------


def test_creates_appointment_and_notifies_screen(scenario):
    response = book(scenario)
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "scheduleUpdated": {"message": "Agendamento criado."}
    }
    [appointment] = appointment_list(scenario)
    assert appointment.patient == scenario["patient"]
    assert appointment.created_by.username == "recepcao"
    assert appointment.series is None


def test_weekly_repeat_creates_the_series(scenario):
    assert book(scenario, repetitions=4).status_code == 204
    created_list = appointment_list(scenario)
    assert len(created_list) == 4
    assert len({a.series for a in created_list}) == 1 and created_list[0].series is not None
    dates = [a.start.date() for a in created_list]
    assert dates == [MONDAY + datetime.timedelta(weeks=n) for n in range(4)]


def test_without_patient_requires_description(scenario):
    response = book(scenario, patient="", description="")
    assert "Informe o paciente ou uma descrição" in errors(response)
    assert book(scenario, patient="", description="Reunião de equipe").status_code == 204
    assert appointment_list(scenario)[0].title == "Reunião de equipe"


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
def test_time_rules(scenario, start, end, message):
    response = book(scenario, start_time=start, end_time=end)
    assert response.status_code == 200
    assert message in errors(response)
    assert appointment_list(scenario) == []


def test_interval_set_by_the_clinic(scenario):
    clinic = scenario["clinic"]
    clinic.schedule_interval = 15
    clinic.save()
    assert book(scenario, start_time="09:15", end_time="09:45").status_code == 204


# --- Conflicts ---------------------------------------------------------------------


def test_conflict_with_same_practitioner(scenario):
    book(scenario)
    response = book(scenario, start_time="09:30", end_time="10:30")
    assert response.status_code == 200
    assert "Conflito de horário" in errors(response)
    assert "Maria Paciente" in errors(response)
    assert len(appointment_list(scenario)) == 1


def test_adjacent_slots_and_other_practitioner_do_not_conflict(scenario):
    book(scenario)
    assert book(scenario, start_time="10:00", end_time="10:30").status_code == 204
    assert book(scenario, start_time="08:30", end_time="09:00").status_code == 204
    assert book(scenario, practitioner=scenario["bruno"].pk).status_code == 204
    assert len(appointment_list(scenario)) == 4


def test_repeat_with_conflict_saves_none(scenario):
    third_week = MONDAY + datetime.timedelta(weeks=2)
    book(scenario, date=third_week.isoformat())
    response = book(scenario, repetitions=4)
    assert response.status_code == 200
    assert third_week.strftime("%d/%m") in errors(response)
    assert "Nada foi gravado" in errors(response)
    assert len(appointment_list(scenario)) == 1


def test_database_prevents_overlap(scenario):
    """Even bypassing the form (e.g. two simultaneous requests), the database refuses."""
    with use_clinic(scenario["clinic"]):
        intervals = services.occurrences(MONDAY, datetime.time(9), datetime.time(10))
        template_ = Appointment(
            practitioner=scenario["ana"], kind=scenario["kind"], description="Primeiro"
        )
        services.create(template_, intervals, None)
        overlapping = services.occurrences(MONDAY, datetime.time(9, 30), datetime.time(10, 30))
        with pytest.raises(IntegrityError), transaction.atomic():
            services.create(template_, overlapping, None)


# --- Editing and deleting ----------------------------------------------------------


def test_editing_moves_time_without_conflicting_with_itself(scenario):
    book(scenario)
    [appointment] = appointment_list(scenario)
    url = reverse("schedule:edit", args=[appointment.pk])
    form_page = scenario["client"].get(url)
    assert form_page.context["form"].initial["start_time"] == datetime.time(9)
    assert "repetitions" not in form_page.context["form"].fields
    response = scenario["client"].post(url, data(scenario, start_time="09:30", end_time="10:30"))
    assert response.status_code == 204
    appointment.refresh_from_db()
    assert appointment.start.astimezone().time() == datetime.time(9, 30)


def test_cancelled_slot_takes_another_patient_keeping_who_cancelled(scenario):
    """Round 2: the cancelled appointment covers the freed slot on the calendar, and changing
    its patient overwrote the record of who cancelled."""
    book(scenario)
    [appointment] = appointment_list(scenario)
    user_client = scenario["client"]
    user_client.post(reverse("schedule:status", args=[appointment.pk]), {"status": "cancelled"})
    window = user_client.get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    assert "Agendar outro paciente neste horário" in window
    assert (
        f"{reverse('schedule:new')}?practitioner={scenario['ana'].pk}&amp;date={MONDAY}" in window
    )
    with use_clinic(scenario["clinic"]):
        other = Patient.objects.create(name="Outro Paciente")
    exchange = user_client.post(
        reverse("schedule:edit", args=[appointment.pk]), data(scenario, patient=other.pk)
    )
    assert "patient" in exchange.context["form"].errors
    new_appointment = user_client.post(reverse("schedule:new"), data(scenario, patient=other.pk))
    assert new_appointment.status_code == 204
    with use_clinic(scenario["clinic"]):
        names = sorted((a.patient.name, a.status) for a in Appointment.objects.all())
    assert names == [("Maria Paciente", "cancelled"), ("Outro Paciente", "booked")]


def test_delete_one_or_the_series_from_then_on(scenario, create_user, client_for):
    book(scenario, repetitions=4)
    created_list = appointment_list(scenario)
    admin = client_for(create_user("admin", scenario["clinic"], Role.ADMIN))

    admin.post(reverse("schedule:delete", args=[created_list[0].pk]), {"scope": "este"})
    assert len(appointment_list(scenario)) == 3

    page = admin.get(reverse("schedule:delete", args=[created_list[1].pk])).content.decode()
    assert "os próximos 2" in page
    response = admin.post(reverse("schedule:delete", args=[created_list[1].pk]), {"scope": "serie"})
    assert json.loads(response["HX-Trigger"])["scheduleUpdated"]["message"] == (
        "3 agendamentos excluídos."
    )
    assert appointment_list(scenario) == []


def test_archived_patient_leaves_suggestions_but_stays_on_schedule(
    scenario, create_user, client_for
):
    book(scenario)
    with use_clinic(scenario["clinic"]):
        Patient.objects.filter(pk=scenario["patient"].pk).update(archived=True)
    suggestions = scenario["client"].get(reverse("patients:suggestions"), {"q": "maria"})
    assert "Maria Paciente" not in suggestions.content.decode()
    period_ = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    events = scenario["client"].get(
        reverse("schedule:events"), {**period_, "practitioner": scenario["ana"].pk}
    )
    assert [e["title"] for e in events.json()] == ["Maria Paciente"]  # history kept


def test_permanent_deletion_removes_patient_from_appointments(scenario, create_user, client_for):
    book(scenario)
    admin = client_for(create_user("admin", scenario["clinic"], Role.ADMIN))
    patient = scenario["patient"]
    admin.post(reverse("patients:archive", args=[patient.pk]))
    assert admin.post(reverse("patients:delete", args=[patient.pk])).status_code == 302
    [appointment] = appointment_list(scenario)
    assert appointment.patient is None
    # The slot stays taken, without the notes (they may hold personal data).
    assert appointment.description == f"Paciente excluído (código {patient.pk})"
    with use_clinic(scenario["clinic"]):
        assert not Patient.objects.filter(pk=patient.pk).exists()


# --- Calendar feeds ----------------------------------------------------------------


def test_period_events_in_json(scenario):
    book(scenario)
    book(scenario, date=(MONDAY + datetime.timedelta(weeks=1)).isoformat())
    response = scenario["client"].get(
        reverse("schedule:events"),
        {
            "practitioner": scenario["ana"].pk,
            "start": f"{MONDAY}T00:00:00-03:00",
            "end": f"{MONDAY + datetime.timedelta(days=7)}T00:00:00-03:00",
        },
    )
    [event] = response.json()
    assert event["title"] == "Maria Paciente"
    assert event["start"].startswith(f"{MONDAY}T09:00:00")
    assert event["backgroundColor"] == "#f7a5a5"
    assert event["extendedProps"]["kind"] == "Cirurgia"


def test_events_with_invalid_parameters(scenario):
    url = reverse("schedule:events")
    assert scenario["client"].get(url, {"practitioner": "x"}).status_code == 400
    long = {"practitioner": 1, "start": "2031-01-01", "end": "2031-12-31"}
    assert scenario["client"].get(url, long).status_code == 400


def test_birthdays_in_the_period(scenario):
    with use_clinic(scenario["clinic"]):
        Patient.objects.create(name="Aniversariante", birth_date=datetime.date(1990, 3, 5))
        Patient.objects.create(name="Inativo", birth_date=datetime.date(1990, 3, 5), active=False)
    response = scenario["client"].get(
        reverse("schedule:birthdays"),
        {"start": f"{MONDAY}T00:00:00", "end": f"{MONDAY + datetime.timedelta(days=7)}T00:00:00"},
    )
    assert response.json() == {"2031-03-05": 1}
    results = scenario["client"].get(reverse("schedule:birthdays_today"), {"date": "2031-03-05"})
    assert "Aniversariante" in results.content.decode()
    assert "completa 41 anos" in results.content.decode()


def test_calendar_opens_on_chosen_practitioner(scenario):
    page = scenario["client"].get(
        reverse("schedule:calendar"), {"practitioner": scenario["bruno"].pk}
    )
    assert page.context["practitioner"] == scenario["bruno"]
    config = page.context["schedule_settings"]
    assert config["interval"] == 30 and config["start"] == "07:30:00"
    assert config["can"] == {"create": True, "change": True}
    # The choice is remembered for the next visit.
    assert (
        scenario["client"].get(reverse("schedule:calendar")).context["practitioner"]
        == scenario["bruno"]
    )


# --- Isolation and permissions -----------------------------------------------------


def test_schedule_of_another_clinic_is_invisible(scenario, clinic_b, create_practitioner):
    of_b = create_practitioner(clinic_b, "Dr. B")
    with use_clinic(clinic_b):
        kind_b = AppointmentType.objects.get(name="Cirurgia")
        patient_b = Patient.objects.create(name="Paciente B")
        [appointment_b] = services.create(
            Appointment(practitioner=of_b, kind=kind_b, patient=patient_b),
            services.occurrences(MONDAY, datetime.time(9), datetime.time(10)),
            None,
        )
    user_client = scenario["client"]
    events = user_client.get(
        reverse("schedule:events"),
        {"practitioner": of_b.pk, "start": f"{MONDAY}T00:00:00", "end": f"{MONDAY}T23:00:00"},
    ).json()
    assert events == []
    assert user_client.get(reverse("schedule:edit", args=[appointment_b.pk])).status_code == 404
    # Ids from another clinic are not accepted in the form either.
    response = book(scenario, practitioner=of_b.pk, kind=kind_b.pk, patient=patient_b.pk)
    assert set(response.context["form"].errors) >= {"practitioner", "kind", "patient"}


def dra_ana_client(scenario, create_user, client_for):
    """A practitioner user linked to Dra. Ana's record."""
    user = create_user("dra", scenario["clinic"], Role.PRACTITIONER)
    with use_clinic(scenario["clinic"]):
        Practitioner.objects.filter(pk=scenario["ana"].pk).update(user=user)
    return client_for(user)


def test_practitioner_books_but_does_not_delete(scenario, create_user, client_for):
    user_client = dra_ana_client(scenario, create_user, client_for)
    assert user_client.post(reverse("schedule:new"), data(scenario)).status_code == 204
    [appointment] = appointment_list(scenario)
    assert user_client.post(reverse("schedule:delete", args=[appointment.pk])).status_code == 403
    form_page = user_client.get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    assert "Excluir" not in form_page


def test_practitioner_sees_only_own_schedule(scenario, create_user, client_for):
    assert book(scenario, practitioner=scenario["bruno"].pk).status_code == 204
    [of_bruno] = appointment_list(scenario)
    # The front desk sees every practitioner (checked first: the test client is shared).
    response = scenario["client"].get(reverse("schedule:calendar"))
    assert len(response.context["practitioners"]) == 2
    user_client = dra_ana_client(scenario, create_user, client_for)

    response = user_client.get(reverse("schedule:calendar"), {"practitioner": scenario["bruno"].pk})
    assert [p.name for p in response.context["practitioners"]] == ["Dra. Ana"]
    assert response.context["practitioner"] == scenario["ana"]
    period_ = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    events = user_client.get(
        reverse("schedule:events"), {**period_, "practitioner": scenario["bruno"].pk}
    )
    assert events.json() == []
    assert user_client.get(reverse("schedule:edit", args=[of_bruno.pk])).status_code == 404

    response = user_client.post(
        reverse("schedule:new"),
        data(scenario, practitioner=scenario["bruno"].pk, start_time="11:00", end_time="12:00"),
    )
    assert response.status_code == 200
    assert "practitioner" in response.context["form"].errors


def test_practitioner_without_linked_profile_sees_no_schedule(scenario, create_user, client_for):
    user_client = client_for(create_user("sem_cadastro", scenario["clinic"], Role.PRACTITIONER))
    response = user_client.get(reverse("schedule:calendar"))
    assert response.context["practitioners"] == []
    assert "não está ligado a um cadastro de profissional" in response.content.decode()


def test_patient_suggestions_only_from_the_clinic(scenario, clinic_b):
    with use_clinic(clinic_b):
        Patient.objects.create(name="Maria de Outra Clínica")
    content = (
        scenario["client"].get(reverse("patients:suggestions"), {"q": "maria"}).content.decode()
    )
    assert "Maria Paciente" in content
    assert "Outra Clínica" not in content


def test_clinic_filter_is_decided_at_run_time(clinic_a):
    # Building a queryset (e.g. form field choices at import time) must not fail...
    query = Appointment.objects.filter(description="x")
    assert AppointmentForm.base_fields["practitioner"].queryset is not None
    # ...but running it without a current clinic must.
    with pytest.raises(NoCurrentClinic):
        list(query)
    with use_clinic(clinic_a):
        assert list(query) == []


def test_period_with_and_without_time_zone_mixed(scenario):
    response = scenario["client"].get(
        reverse("schedule:events"),
        {
            "start": "2031-03-03T00:00:00",
            "end": "2031-03-10T00:00:00-03:00",
            "practitioner": scenario["ana"].pk,
        },
    )
    assert response.status_code == 200


# --- Patient record history --------------------------------------------------------


def test_record_shows_upcoming_and_past(scenario, create_user, client_for):
    now = timezone.localtime()
    past = now.date() - datetime.timedelta(days=7)
    with use_clinic(scenario["clinic"]):
        Appointment.objects.create(
            practitioner=scenario["ana"],
            kind=scenario["kind"],
            patient=scenario["patient"],
            start=services.timestamp(past, datetime.time(9)),
            end=services.timestamp(past, datetime.time(10)),
        )
    book(scenario)  # 2031, Dra. Ana
    book(scenario, practitioner=scenario["bruno"].pk, start_time="11:00", end_time="12:00")
    url = reverse("patients:record", args=[scenario["patient"].pk])

    history = scenario["client"].get(url).context["appointments"]
    assert history["total"] == 3
    assert [a.practitioner.name for a in history["upcoming"]] == ["Dra. Ana", "Dr. Bruno"]
    assert [a.start.date() for a in history["past"]] == [past]

    # Practitioners see only their own appointments in the record too.
    user_client = dra_ana_client(scenario, create_user, client_for)
    response = user_client.get(url)
    history = response.context["appointments"]
    assert history["total"] == 2
    assert {a.practitioner.name for a in history["upcoming"]} == {"Dra. Ana"}
    assert "?practitioner=" in response.content.decode()


# --- Simulated activity --------------------------------------------------------------


def test_simulate_activity_respects_taken_slots(scenario):
    # A real appointment today at 09:00 for Dra. Ana must stay untouched.
    today = timezone.localdate()
    with use_clinic(scenario["clinic"]):
        Patient.objects.create(name="Arquivado", archived=True)
        existing = Appointment.objects.create(
            practitioner=scenario["ana"],
            kind=scenario["kind"],
            start=services.timestamp(today, datetime.time(9)),
            end=services.timestamp(today, datetime.time(10)),
            description="Real",
        )
    with pytest.raises(CommandError):
        call_command("simulate_activity", clinic=scenario["clinic"].name)
    call_command("simulate_activity", clinic=scenario["clinic"].name, confirm=True)

    with use_clinic(scenario["clinic"]):
        new_items = Appointment.objects.exclude(pk=existing.pk)
        assert new_items.count() > 0
        assert not new_items.filter(
            practitioner=scenario["ana"], start__lt=existing.end, end__gt=existing.start
        ).exists()
        assert not new_items.filter(patient__archived=True).exists()
        assert new_items.filter(kind__name="Ocupado").count() == 0
        assert Recall.objects.count() == 80
        assert not Recall.objects.filter(patient__archived=True).exists()
        # Cheques are not used anymore, not even in made-up data.
        assert Payment.objects.exists()
        assert not Payment.objects.filter(method=Payment.Method.CHEQUE).exists()


def test_simulate_only_recalls(scenario):
    call_command(
        "simulate_activity",
        clinic=scenario["clinic"].name,
        no_schedule=True,
        recalls=5,
        confirm=True,
    )
    with use_clinic(scenario["clinic"]):
        assert not Appointment.objects.exists()
        assert Recall.objects.count() == 5


# --- Came / missed / cancelled (0.24.0) ---------------------------------------------------


def appointment_at(scenario, day, hour=9, patient=True, practitioner="ana"):
    with use_clinic(scenario["clinic"]):
        return Appointment.objects.create(
            practitioner=scenario[practitioner],
            kind=scenario["kind"],
            patient=scenario["patient"] if patient else None,
            description="" if patient else "Bloqueado",
            start=services.timestamp(day, datetime.time(hour)),
            end=services.timestamp(day, datetime.time(hour + 1)),
        )


def mark(scenario, appointment, status, htmx=True, user_client=None):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return (user_client or scenario["client"]).post(
        reverse("schedule:status", args=[appointment.pk]), {"status": status}, **headers
    )


def status_of(scenario, appointment):
    with use_clinic(scenario["clinic"]):
        return Appointment.objects.get(pk=appointment.pk).status


def test_marks_attendance_and_no_show_from_the_day(scenario):
    today = timezone.localdate()
    appointment = appointment_at(scenario, today)
    response = mark(scenario, appointment, "attended")
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "scheduleUpdated": {"message": "Maria Paciente compareceu."}
    }
    assert status_of(scenario, appointment) == "attended"
    assert mark(scenario, appointment, "booked").status_code == 204
    assert status_of(scenario, appointment) == "booked"

    # The appointment window shows the buttons; a future one only offers "cancelled".
    window = scenario["client"].get(reverse("schedule:edit", args=[appointment.pk]))
    assert "Compareceu" in window.content.decode()
    future = appointment_at(scenario, MONDAY)
    window = scenario["client"].get(reverse("schedule:edit", args=[future.pk])).content.decode()
    assert '"status": "missed"' not in window and '"status": "cancelled"' in window
    response = mark(scenario, future, "missed")
    assert response.status_code == 200
    assert "a partir do dia do atendimento" in response.context["status_error"]
    assert status_of(scenario, future) == "booked"


def test_status_button_sends_what_the_view_reads(scenario):
    """The window's buttons post their hx-vals: pressing one must change the status."""
    appointment = appointment_at(scenario, timezone.localdate())
    window = (
        scenario["client"].get(reverse("schedule:edit", args=[appointment.pk])).content.decode()
    )
    button = re.search(r'hx-post="([^"]+)" hx-vals=\'([^\']+)\'[^>]*>✓', window)
    assert button, "no Compareceu button in the window"
    response = scenario["client"].post(button[1], json.loads(button[2]), HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert status_of(scenario, appointment) == "attended"


def test_invalid_status_and_slot_without_patient_are_refused(scenario):
    today = timezone.localdate()
    lockout = appointment_at(scenario, today, patient=False)
    response = mark(scenario, lockout, "attended", htmx=False)
    assert response.status_code == 302 and response.url == reverse("home")
    assert status_of(scenario, lockout) == "booked"
    appointment = appointment_at(scenario, today, hour=11)
    mark(scenario, appointment, "chegou")
    assert status_of(scenario, appointment) == "booked"
    assert (
        scenario["client"].get(reverse("schedule:status", args=[appointment.pk])).status_code == 405
    )


def test_cancelled_frees_the_slot(scenario):
    book(scenario)
    [first] = appointment_list(scenario)
    assert mark(scenario, first, "cancelled").status_code == 204
    # The slot is free again for another patient, also for the database constraint.
    assert book(scenario).status_code == 204
    assert len(appointment_list(scenario)) == 2
    # Undoing the cancellation would double-book: refused.
    response = mark(scenario, first, "booked")
    assert "já foi ocupado" in response.context["status_error"]
    assert status_of(scenario, first) == "cancelled"
    # Editing the cancelled one does not conflict with the new one either.
    response = scenario["client"].post(
        reverse("schedule:edit", args=[first.pk]), data(scenario, description="Remarcar")
    )
    assert response.status_code == 204


def test_rescheduling_to_future_or_removing_patient_clears_attendance(scenario):
    today = timezone.localdate()
    appointment = appointment_at(scenario, today)
    mark(scenario, appointment, "missed")
    response = scenario["client"].post(
        reverse("schedule:edit", args=[appointment.pk]), data(scenario)
    )
    assert response.status_code == 204
    assert status_of(scenario, appointment) == "booked"

    other = appointment_at(scenario, today, hour=11)
    mark(scenario, other, "attended")
    without_patient = data(
        scenario,
        patient="",
        description="Bloqueado",
        date=today.isoformat(),
        start_time="11:00",
        end_time="12:00",
    )
    scenario["client"].post(reverse("schedule:edit", args=[other.pk]), without_patient)
    assert status_of(scenario, other) == "booked"


def test_practitioner_marks_only_own_schedule(scenario, create_user, client_for):
    today = timezone.localdate()
    of_bruno = appointment_at(scenario, today, practitioner="bruno")
    of_ana = appointment_at(scenario, today)
    user_client = dra_ana_client(scenario, create_user, client_for)
    assert mark(scenario, of_bruno, "attended", user_client=user_client).status_code == 404
    assert mark(scenario, of_ana, "attended", user_client=user_client).status_code == 204


def test_events_carry_the_status(scenario):
    appointment = appointment_at(scenario, timezone.localdate())
    mark(scenario, appointment, "missed")
    today = timezone.localdate()
    response = scenario["client"].get(
        reverse("schedule:events"),
        {
            "practitioner": scenario["ana"].pk,
            "start": today.isoformat(),
            "end": (today + datetime.timedelta(days=1)).isoformat(),
        },
    )
    [event] = response.json()
    assert event["classNames"] == ["status-missed"]
    assert event["extendedProps"]["status_name"] == "Faltou"


def test_default_types_show_in_user_language(scenario):
    """The default types are saved in Portuguese and shown translated; a type the clinic
    typed itself is shown as saved."""
    user_client = scenario["client"]
    with use_clinic(scenario["clinic"]):
        AppointmentType.objects.create(name="Clareamento a laser", color="#ffffff")

    user_client.post(reverse("change_language"), {"language": "en"})
    legend = user_client.get(reverse("schedule:calendar")).content.decode()
    assert ">Surgery<" in legend and ">Orthodontics<" in legend
    assert ">Cirurgia<" not in legend
    assert ">Clareamento a laser<" in legend
    assert ">Surgery</option>" in user_client.get(reverse("schedule:new")).content.decode()

    user_client.post(reverse("change_language"), {"language": "es"})
    assert ">Cirugía<" in user_client.get(reverse("schedule:calendar")).content.decode()
    with use_clinic(scenario["clinic"]):
        assert AppointmentType.objects.filter(name="Cirurgia").exists()  # data untouched
