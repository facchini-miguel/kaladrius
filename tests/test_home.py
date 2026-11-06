"""Home page summary of the day (0.24.0)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.estimates.models import Estimate
from apps.finance import services as financeiro
from apps.finance.models import CashRegister, Category, Entry, FinancialAccount
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# A Wednesday, 10:30 in the clinic's time zone.
HOJE = datetime.date(2031, 3, 5)
AGORA = timezone.make_aware(datetime.datetime(2031, 3, 5, 10, 30))


def day(number, month=3):
    return datetime.date(2031, month, number)


@pytest.fixture
def cenario(monkeypatch, clinica_a, criar_profissional, criar_usuario):
    monkeypatch.setattr(timezone, "now", lambda: AGORA)
    ana = criar_profissional(clinica_a, "Dra. Ana")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    usuarios = {
        "admin": criar_usuario("admin", clinica_a, Role.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Role.FRONT_DESK),
        "dra": criar_usuario("dra", clinica_a, Role.PRACTITIONER),
    }
    with use_clinic(clinica_a):
        Practitioner.objects.filter(pk=ana.pk).update(user=usuarios["dra"])
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

        def agendar(date, hour, practitioner=ana, patient=maria, status="agendado"):
            Appointment.objects.create(
                practitioner=practitioner,
                kind=kind,
                patient=patient,
                description="" if patient else "Bloqueado",
                status=status,
                start=agenda.timestamp(date, datetime.time(hour)),
                end=agenda.timestamp(date, datetime.time(hour + 1)),
            )

        agendar(HOJE, 8, status="compareceu")
        agendar(HOJE, 9, status="faltou")
        agendar(HOJE, 10, practitioner=bruno, patient=joao)  # started, nobody marked it
        agendar(HOJE, 11)
        agendar(HOJE, 14, status="desmarcou")
        agendar(HOJE, 16, patient=None)
        agendar(day(3), 9, status="compareceu")
        agendar(day(4), 9, status="faltou")
        agendar(day(27, 2), 9, status="faltou")  # last month: not in this month's rate

        for date, done, patient in [
            (HOJE, False, maria),
            (day(1), False, maria),
            (day(2), True, maria),
            (HOJE, False, archived),
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
        receita = Category.objects.get(name="Tratamento")
        despesa = Category.objects.get(name="Outras despesas")

        def lancar(kind, amount, parcelas, due_date, category, **fields):
            entry = financeiro.create_entry(
                clinic=clinica_a,
                kind=kind,
                description="Teste",
                category=category,
                total_amount=Decimal(amount),
                parcelas=parcelas,
                primeiro_vencimento=due_date,
                user=usuarios["admin"],
                **fields,
            )
            return list(entry.parcelas.order_by("number"))

        def pagar(installment, amount, date, method="pix"):
            financeiro.receive(
                installment,
                user=usuarios["admin"],
                amount=Decimal(amount),
                date=date,
                method=method,
                account=cash_register,
            )

        # Due 05/01, 05/02 (overdue) and today; the first one is paid today.
        primeira, _segunda, _terceira = lancar(
            Entry.Kind.RECEIVABLE, "300", 3, day(5, 1), receita, patient=maria
        )
        pagar(primeira, "100", HOJE)
        [fevereiro] = lancar(Entry.Kind.RECEIVABLE, "200", 1, day(3, 2), receita, patient=joao)
        pagar(fevereiro, "200", day(3, 2), method="dinheiro")
        [conta_de_luz] = lancar(Entry.Kind.PAYABLE, "50", 1, HOJE, despesa, payer="Luz")
        pagar(conta_de_luz, "50", HOJE)
        lancar(Entry.Kind.PAYABLE, "80", 1, day(10), despesa, payer="Aluguel")
        lancar(Entry.Kind.PAYABLE, "999", 1, day(20), despesa, payer="Longe")
        CashRegister.objects.create(
            account=cash_register, opening_amount=Decimal("0"), opened_by=usuarios["admin"]
        )
    return {"clinic": clinica_a, **usuarios}


def start(cenario, cliente_de, quem):
    return cliente_de(cenario[quem]).get(reverse("home"))


def test_reception_sees_the_day_without_expenses(cenario, cliente_de):
    response = start(cenario, cliente_de, "recepcao")
    painel = response.context["dashboard"]
    dia_ = painel["schedule"]
    assert len(dia_["items"]) == 6 and dia_["show_practitioner"]
    assert (dia_["patients"], dia_["attended"], dia_["missed"]) == (4, 1, 1)
    assert (dia_["cancelled"], dia_["upcoming"], dia_["unmarked"]) == (1, 1, 1)
    assert dia_["next"].patient.name == "João Paciente"  # 10:00–11:00, still going on
    # Month so far: came 08:00 today and on the 3rd; missed 09:00 today and on the 4th.
    assert (dia_["missed_pct_month"], dia_["booked_month"]) == (50, 4)

    recebimentos = painel["receipts"]
    assert recebimentos["received"] == Decimal("100")
    assert recebimentos["by_method"] == [("Pix", Decimal("100"))]
    assert (recebimentos["receivable"], recebimentos["receivable_count"]) == (Decimal("100"), 1)
    assert [cash_register.account.name for cash_register in recebimentos["cash_registers"]] == [
        "Caixa"
    ]
    assert "finance" not in painel

    content = response.content.decode()
    assert "Bom dia, recepcao" in content
    assert "Recebido hoje" in content and "Pago hoje" not in content
    assert "Saldo nas contas" not in content
    assert reverse("schedule:status", args=[dia_["next"].pk]) in content


def test_admin_sees_day_and_month_result(cenario, cliente_de):
    painel = start(cenario, cliente_de, "admin").context["dashboard"]
    fin = painel["finance"]
    assert fin["paid_today"] == Decimal("50") and fin["result_today"] == Decimal("50")
    assert (fin["received_month"], fin["paid_month"]) == (Decimal("100"), Decimal("50"))
    assert fin["result_month"] == Decimal("50")
    # Same days of February (1st to 5th): the 200 received on the 3rd.
    assert (fin["previous_start"], fin["previous_until"]) == (day(1, 2), day(5, 2))
    assert fin["previous_result"] == Decimal("200")
    assert (fin["overdue"], fin["overdue_count"]) == (Decimal("100"), 1)
    assert (fin["payable"], fin["payable_count"]) == (Decimal("80"), 1)
    assert fin["account_balances"] == Decimal("250")


def test_practitioner_sees_only_own_schedule_and_no_amounts(cenario, cliente_de):
    response = start(cenario, cliente_de, "dra")
    painel = response.context["dashboard"]
    assert {a.practitioner.name for a in painel["schedule"]["items"]} == {"Dra. Ana"}
    assert not painel["schedule"]["show_practitioner"]
    assert painel["schedule"]["next"].start.astimezone().hour == 11
    assert "receipts" not in painel and "finance" not in painel
    # Estimates show their totals (practitioners write them), but no money of the clinic.
    content = response.content.decode()
    assert "Recebido hoje" not in content and "Caixa do dia" not in content


def test_lists_of_recalls_birthdays_and_estimates(cenario, cliente_de):
    painel = start(cenario, cliente_de, "recepcao").context["dashboard"]
    rechamadas = painel["recalls"]
    assert [r.date for r in rechamadas["items"]] == [day(1), HOJE]
    assert (rechamadas["total"], rechamadas["late"]) == (2, 1)
    assert [(p.name, age) for p, age in painel["birthdays"]] == [("Maria Paciente", 41)]
    assert [o.valid_until for o in painel["estimates"]] == [day(8)]


def test_completing_recall_and_marking_attendance_return_home(cenario, cliente_de):
    cliente = cliente_de(cenario["recepcao"])
    painel = cliente.get(reverse("home")).context["dashboard"]
    rechamada = painel["recalls"]["items"][0]
    response = cliente.post(
        reverse("recalls:complete", args=[rechamada.pk]), {"next": reverse("home")}
    )
    assert response.url == reverse("home")
    proximo = painel["schedule"]["next"]
    response = cliente.post(
        reverse("schedule:status", args=[proximo.pk]), {"status": "compareceu"}, follow=True
    )
    assert "João Paciente compareceu." in response.content.decode()
    assert response.context["dashboard"]["schedule"]["attended"] == 2
    assert response.context["dashboard"]["recalls"]["total"] == 1


def test_no_clinic_means_no_summary(cenario, criar_usuario, cliente_de):
    response = cliente_de(criar_usuario("solto")).get(reverse("home"))
    assert "painel" not in response.context
    assert "não tem acesso a nenhuma clínica ativa" in response.content.decode()


def test_greeting_by_time_of_day(monkeypatch, criar_usuario, cliente_de):
    user = criar_usuario("maria")
    for hour, saudacao in [(7, "Bom dia"), (13, "Boa tarde"), (20, "Boa noite")]:
        timestamp = timezone.make_aware(datetime.datetime(2031, 3, 5, hour))
        monkeypatch.setattr(timezone, "now", lambda timestamp=timestamp: timestamp)
        # Logged in at the patched time, so the session is not seen as expired.
        content = cliente_de(user).get(reverse("home")).content.decode()
        assert f"{saudacao}, maria" in content
