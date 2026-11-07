"""Home page summary of the day (0.24.0)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.estimates.models import Estimate
from apps.finance import services as finance_services
from apps.finance.models import CashRegister, Category, Entry, FinancialAccount
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# A Wednesday, 10:30 in the clinic's time zone.
TODAY = datetime.date(2031, 3, 5)
NOW = timezone.make_aware(datetime.datetime(2031, 3, 5, 10, 30))


def day(number, month=3):
    return datetime.date(2031, month, number)


@pytest.fixture
def scenario(monkeypatch, clinic_a, create_practitioner, create_user):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    ana = create_practitioner(clinic_a, "Dra. Ana")
    bruno = create_practitioner(clinic_a, "Dr. Bruno")
    users = {
        "admin": create_user("admin", clinic_a, Role.ADMIN),
        "reception": create_user("recepcao", clinic_a, Role.FRONT_DESK),
        "dra": create_user("dra", clinic_a, Role.PRACTITIONER),
    }
    with use_clinic(clinic_a):
        Practitioner.objects.filter(pk=ana.pk).update(user=users["dra"])
        kind = AppointmentType.objects.get(name="Cirurgia")
        maria = Patient.objects.create(
            name="Maria Paciente",
            birth_date=day(5, 3).replace(year=1990),
            mobile_phone="11987654321",
        )
        joao = Patient.objects.create(name="João Paciente")
        archived = Patient.objects.create(
            name="Paciente Arquivado", archived=True, birth_date=day(5).replace(year=1980)
        )

        def book(date, hour, practitioner=ana, patient=maria, status="booked"):
            Appointment.objects.create(
                practitioner=practitioner,
                kind=kind,
                patient=patient,
                description="" if patient else "Bloqueado",
                status=status,
                start=agenda.timestamp(date, datetime.time(hour)),
                end=agenda.timestamp(date, datetime.time(hour + 1)),
            )

        book(TODAY, 8, status="attended")
        book(TODAY, 9, status="missed")
        book(TODAY, 10, practitioner=bruno, patient=joao)  # started, nobody marked it
        book(TODAY, 11)
        book(TODAY, 14, status="cancelled")
        book(TODAY, 16, patient=None)
        book(day(3), 9, status="attended")
        book(day(4), 9, status="missed")
        book(day(27, 2), 9, status="missed")  # last month: not in this month's rate

        for date, done, patient in [
            (TODAY, False, maria),
            (day(1), False, maria),
            (day(2), True, maria),
            (TODAY, False, archived),
            (day(10), False, maria),
        ]:
            Recall.objects.create(patient=patient, date=date, description="Revisão", done=done)

        for patient, valid_until, status in [
            (maria, day(8), Estimate.Status.OPEN),
            (maria, day(20), Estimate.Status.OPEN),
            (maria, day(6), Estimate.Status.APPROVED),
            (archived, day(6), Estimate.Status.OPEN),
            (maria, day(4), Estimate.Status.OPEN),
        ]:
            Estimate.objects.create(
                patient=patient, date=day(1), valid_until=valid_until, status=status
            )

        cash_register = FinancialAccount.objects.get(name="Caixa")
        income = Category.objects.get(name="Tratamento")
        expense = Category.objects.get(name="Outras despesas")

        def post_entry(kind, amount, installments, due_date, category, **fields):
            entry = finance_services.create_entry(
                clinic=clinic_a,
                kind=kind,
                description="Teste",
                category=category,
                total_amount=Decimal(amount),
                installments=installments,
                first_due_date=due_date,
                user=users["admin"],
                **fields,
            )
            return list(entry.installments.order_by("number"))

        def pay_(installment, amount, date, method="pix"):
            finance_services.receive(
                installment,
                user=users["admin"],
                amount=Decimal(amount),
                date=date,
                method=method,
                account=cash_register,
            )

        # Due 05/01, 05/02 (overdue) and today; the first one is paid today.
        first_one, _second, _third = post_entry(
            Entry.Kind.RECEIVABLE, "300", 3, day(5, 1), income, patient=maria
        )
        pay_(first_one, "100", TODAY)
        [february] = post_entry(Entry.Kind.RECEIVABLE, "200", 1, day(3, 2), income, patient=joao)
        pay_(february, "200", day(3, 2), method="cash")
        [power_bill] = post_entry(Entry.Kind.PAYABLE, "50", 1, TODAY, expense, payer="Luz")
        pay_(power_bill, "50", TODAY)
        post_entry(Entry.Kind.PAYABLE, "80", 1, day(10), expense, payer="Aluguel")
        post_entry(Entry.Kind.PAYABLE, "999", 1, day(20), expense, payer="Longe")
        CashRegister.objects.create(
            account=cash_register, opening_amount=Decimal("0"), opened_by=users["admin"]
        )
    return {"clinic": clinic_a, **users}


def start(scenario, client_for, who):
    return client_for(scenario[who]).get(reverse("home"))


def test_reception_sees_the_day_without_expenses(scenario, client_for):
    response = start(scenario, client_for, "reception")
    dashboard = response.context["dashboard"]
    day_ = dashboard["schedule"]
    assert len(day_["items"]) == 6 and day_["show_practitioner"]
    assert (day_["patients"], day_["attended"], day_["missed"]) == (4, 1, 1)
    assert (day_["cancelled"], day_["upcoming"], day_["unmarked"]) == (1, 1, 1)
    assert day_["next"].patient.name == "João Paciente"  # 10:00–11:00, still going on
    # Month so far: came 08:00 today and on the 3rd; missed 09:00 today and on the 4th.
    assert (day_["missed_pct_month"], day_["booked_month"]) == (50, 4)

    receipts = dashboard["receipts"]
    assert receipts["received"] == Decimal("100")
    assert receipts["by_method"] == [("Pix", Decimal("100"))]
    assert (receipts["receivable"], receipts["receivable_count"]) == (Decimal("100"), 1)
    assert [cash_register.account.name for cash_register in receipts["cash_registers"]] == ["Caixa"]
    assert "finance" not in dashboard

    content = response.content.decode()
    assert "Bom dia, recepcao" in content
    assert "Recebido hoje" in content and "Pago hoje" not in content
    assert "Saldo nas contas" not in content
    assert reverse("schedule:status", args=[day_["next"].pk]) in content


def test_admin_sees_day_and_month_result(scenario, client_for):
    dashboard = start(scenario, client_for, "admin").context["dashboard"]
    fin_ = dashboard["finance"]
    assert fin_["paid_today"] == Decimal("50") and fin_["result_today"] == Decimal("50")
    assert (fin_["received_month"], fin_["paid_month"]) == (Decimal("100"), Decimal("50"))
    assert fin_["result_month"] == Decimal("50")
    # Same days of February (1st to 5th): the 200 received on the 3rd.
    assert (fin_["previous_start"], fin_["previous_until"]) == (day(1, 2), day(5, 2))
    assert fin_["previous_result"] == Decimal("200")
    assert (fin_["overdue"], fin_["overdue_count"]) == (Decimal("100"), 1)
    assert (fin_["payable"], fin_["payable_count"]) == (Decimal("80"), 1)
    assert fin_["account_balances"] == Decimal("250")


def test_practitioner_sees_only_own_schedule_and_no_amounts(scenario, client_for):
    response = start(scenario, client_for, "dra")
    dashboard = response.context["dashboard"]
    assert {a.practitioner.name for a in dashboard["schedule"]["items"]} == {"Dra. Ana"}
    assert not dashboard["schedule"]["show_practitioner"]
    assert dashboard["schedule"]["next"].start.astimezone().hour == 11
    assert "receipts" not in dashboard and "finance" not in dashboard
    # Estimates show their totals (practitioners write them), but no money of the clinic.
    content = response.content.decode()
    assert "Recebido hoje" not in content and "Caixa do dia" not in content


def test_lists_of_recalls_birthdays_and_estimates(scenario, client_for):
    dashboard = start(scenario, client_for, "reception").context["dashboard"]
    recalls = dashboard["recalls"]
    assert [r.date for r in recalls["items"]] == [day(1), TODAY]
    assert (recalls["total"], recalls["late"]) == (2, 1)
    assert [(p.name, age) for p, age in dashboard["birthdays"]] == [("Maria Paciente", 41)]
    assert [o.valid_until for o in dashboard["estimates"]] == [day(8)]


def test_completing_recall_and_marking_attendance_return_home(scenario, client_for):
    user_client = client_for(scenario["reception"])
    dashboard = user_client.get(reverse("home")).context["dashboard"]
    recall = dashboard["recalls"]["items"][0]
    response = user_client.post(
        reverse("recalls:complete", args=[recall.pk]), {"next": reverse("home")}
    )
    assert response.url == reverse("home")
    next_one = dashboard["schedule"]["next"]
    response = user_client.post(
        reverse("schedule:status", args=[next_one.pk]), {"status": "attended"}, follow=True
    )
    assert "João Paciente compareceu." in response.content.decode()
    assert response.context["dashboard"]["schedule"]["attended"] == 2
    assert response.context["dashboard"]["recalls"]["total"] == 1


def test_no_clinic_means_no_summary(scenario, create_user, client_for):
    response = client_for(create_user("solto")).get(reverse("home"))
    assert "painel" not in response.context
    assert "não tem acesso a nenhuma clínica ativa" in response.content.decode()


def test_greeting_by_time_of_day(monkeypatch, create_user, client_for):
    user = create_user("maria")
    for hour, greeting in [(7, "Bom dia"), (13, "Boa tarde"), (20, "Boa noite")]:
        timestamp = timezone.make_aware(datetime.datetime(2031, 3, 5, hour))
        monkeypatch.setattr(timezone, "now", lambda timestamp=timestamp: timestamp)
        # Logged in at the patched time, so the session is not seen as expired.
        content = client_for(user).get(reverse("home")).content.decode()
        assert f"{greeting}, maria" in content
