import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.patients.models import Patient
from apps.recalls.models import Recall

pytestmark = pytest.mark.django_db
DAY = datetime.date(2031, 3, 5)


@pytest.fixture
def scenario(clinic_a, create_user, client_for):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="João Rechamada")
    return {
        "clinic": clinic_a,
        "patient": patient,
        "client": client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK)),
    }


def recalls(clinic):
    with use_clinic(clinic):
        return list(Recall.objects.order_by("date"))


def create(clinic, patient, date=DAY, **extra):
    with use_clinic(clinic):
        return Recall.objects.create(patient=patient, date=date, description="Revisão", **extra)


def test_creates_recall(scenario):
    response = scenario["client"].post(
        reverse("recalls:new"),
        {
            "patient": scenario["patient"].pk,
            "date": DAY.isoformat(),
            "description": "Revisão 6 meses",
        },
    )
    assert response.status_code == 302
    [recall] = recalls(scenario["clinic"])
    assert recall.description == "Revisão 6 meses" and not recall.done
    assert recall.created_by.username == "recepcao"


def test_patient_is_required(scenario):
    response = scenario["client"].post(
        reverse("recalls:new"), {"date": DAY.isoformat(), "description": "x"}
    )
    assert "Escolha o paciente" in response.content.decode()


def test_new_from_record_returns_to_record(scenario):
    patient_record = reverse("patients:record", args=[scenario["patient"].pk])
    form_page = scenario["client"].get(
        reverse("recalls:new"), {"patient": scenario["patient"].pk, "next": patient_record}
    )
    assert "João Rechamada" in form_page.content.decode()
    response = scenario["client"].post(
        reverse("recalls:new"),
        {
            "patient": scenario["patient"].pk,
            "date": DAY.isoformat(),
            "description": "x",
            "next": patient_record,
        },
    )
    assert response.url == patient_record
    assert "Revisão" not in scenario["client"].get(patient_record).content.decode()  # shows "x"


def test_complete_and_reopen(scenario):
    recall = create(scenario["clinic"], scenario["patient"])
    url = reverse("recalls:complete", args=[recall.pk])
    assert scenario["client"].get(url).status_code == 405
    scenario["client"].post(url)
    recall.refresh_from_db()
    assert recall.done
    scenario["client"].post(url)
    recall.refresh_from_db()
    assert not recall.done


def test_list_filters(scenario):
    clinic, patient = scenario["clinic"], scenario["patient"]
    create(clinic, patient, DAY)
    create(clinic, patient, DAY + datetime.timedelta(days=30), done=True)
    with use_clinic(clinic):
        other = Patient.objects.create(name="Ana Outra")
    create(clinic, other, DAY + datetime.timedelta(days=60))
    url = reverse("recalls:list")

    def names(**params):
        return [r.patient.name for r in scenario["client"].get(url, params).context["page"]]

    assert names() == ["João Rechamada", "Ana Outra"]  # pending, ordered by date
    assert names(status="done") == ["João Rechamada"]
    assert names(status="all", q="ana") == ["Ana Outra"]
    assert names(status="all", since="2031-03-06", until="2031-04-30") == ["João Rechamada"]


def test_overdue_status(scenario):
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    create(scenario["clinic"], scenario["patient"], yesterday)
    assert "Atrasada" in scenario["client"].get(reverse("recalls:list")).content.decode()


def test_summary_and_day_list_for_schedule(scenario):
    clinic, patient = scenario["clinic"], scenario["patient"]
    create(clinic, patient, DAY)
    create(clinic, patient, DAY)
    create(clinic, patient, DAY, done=True)
    summary = scenario["client"].get(
        reverse("recalls:summary"),
        {"start": "2031-03-03T00:00:00-03:00", "end": "2031-03-10T00:00:00-03:00"},
    )
    assert summary.json() == {"2031-03-05": 2}
    day = scenario["client"].get(reverse("recalls:today"), {"date": "2031-03-05"}).content.decode()
    assert day.count("João Rechamada") == 3


def test_schedule_gets_recall_urls(scenario, create_practitioner):
    create_practitioner(scenario["clinic"], "Dra. A")
    urls = scenario["client"].get(reverse("schedule:calendar")).context["schedule_settings"]["urls"]
    assert urls["recalls"] == reverse("recalls:summary")


def test_isolation(scenario, clinic_b):
    with use_clinic(clinic_b):
        patient_b = Patient.objects.create(name="Paciente B")
    of_b = create(clinic_b, patient_b)
    user_client = scenario["client"]
    assert user_client.get(reverse("recalls:edit", args=[of_b.pk])).status_code == 404
    assert user_client.post(reverse("recalls:complete", args=[of_b.pk])).status_code == 404
    assert len(user_client.get(reverse("recalls:list"), {"status": "all"}).context["page"]) == 0
    response = user_client.post(
        reverse("recalls:new"),
        {"patient": patient_b.pk, "date": DAY.isoformat(), "description": "x"},
    )
    assert "patient" in response.context["form"].errors


@pytest.mark.parametrize(("role", "deletes"), [(Role.FRONT_DESK, True), (Role.PRACTITIONER, False)])
def test_delete_permission(role, deletes, scenario, create_user, client_for):
    recall = create(scenario["clinic"], scenario["patient"])
    user_client = client_for(create_user("usuario", scenario["clinic"], role))
    response = user_client.post(reverse("recalls:delete", args=[recall.pk]))
    assert response.status_code == (302 if deletes else 403)


def test_recalls_of_archived_patient_leave_the_screens(scenario, create_user, client_for):
    recall = create(scenario["clinic"], scenario["patient"])
    admin = client_for(create_user("admin", scenario["clinic"], Role.ADMIN))
    admin.post(reverse("patients:archive", args=[scenario["patient"].pk]))
    assert "Maria" not in admin.get(reverse("recalls:list")).content.decode()
    day = admin.get(reverse("recalls:today"), {"date": recall.date.isoformat()})
    assert "Maria" not in day.content.decode()

    # Permanent deletion takes the recalls with it.
    admin.post(reverse("patients:delete", args=[scenario["patient"].pk]))
    with use_clinic(scenario["clinic"]):
        assert not Recall.objects.exists()


# --- Birthdays ---------------------------------------------------------------------


def test_birthdays_of_the_month(scenario):
    clinic = scenario["clinic"]
    with use_clinic(clinic):
        Patient.objects.create(name="Março 20", birth_date=datetime.date(1990, 3, 20))
        Patient.objects.create(name="Março 2", birth_date=datetime.date(2000, 3, 2))
        Patient.objects.create(name="Inativo", birth_date=datetime.date(1990, 3, 1), active=False)
        Patient.objects.create(name="Nascido em abril", birth_date=datetime.date(1990, 4, 1))
    response = scenario["client"].get(reverse("patients:birthdays"), {"month": 3})
    assert [p.name for p, _ in response.context["rows"]] == ["Março 2", "Março 20"]
    assert "Nascido em abril" not in response.content.decode()
    today = timezone.localdate()
    default = scenario["client"].get(reverse("patients:birthdays"))
    assert default.context["month"] == today.month


def test_birthdays_require_permission_and_clinic(create_user, client_for):
    response = client_for(create_user("solto")).get(reverse("patients:birthdays"))
    assert response.status_code == 403


def test_tampered_patient_in_form_shows_error(scenario):
    response = scenario["client"].post(
        reverse("recalls:new"), {"patient": "abc", "date": "2031-03-05", "description": "x"}
    )
    assert response.status_code == 200
    assert response.context["form"].errors["patient"]
    assert recalls(scenario["clinic"]) == []
