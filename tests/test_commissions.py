"""Practitioner commission (0.19.0): percentage of what is received, paid once."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance import commissions, services
from apps.finance.models import Category, Commission, Entry, FinancialAccount, Payment
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()
YESTERDAY = TODAY - datetime.timedelta(days=1)


@pytest.fixture
def scenario(clinic_a, create_user, client_for):
    admin = create_user("admin", clinic_a, Role.ADMIN)
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paulo Paciente")
        dra = Practitioner.objects.create(name="Dra. Ana", commission_percentage=Decimal("40"))
        dr = Practitioner.objects.create(name="Dr. Beto")
        treatment = Category.objects.get(name="Tratamento")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        category = Category.objects.get(name="Comissões")
    return {
        "clinic": clinic_a,
        "patient": patient,
        "dra": dra,
        "dr": dr,
        "treatment": treatment,
        "cash_register": cash_register,
        "category": category,
        "admin": admin,
        "reception": create_user("recepcao", clinic_a, Role.FRONT_DESK),
        # The test client is shared: log in as the administrator by default.
        "client": client_for(admin),
        "client_for": client_for,
    }


def receive(scenario, amount, practitioner, date=YESTERDAY, interest="0"):
    """A receivable for `valor` paid in full on `data`."""
    with use_clinic(scenario["clinic"]):
        entry = services.create_entry(
            clinic=scenario["clinic"],
            kind=Entry.Kind.RECEIVABLE,
            patient=scenario["patient"],
            practitioner=practitioner,
            description="Tratamento",
            category=scenario["treatment"],
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=scenario["admin"],
        )
        return services.receive(
            entry.installments.get(),
            user=scenario["admin"],
            amount=Decimal(amount) + Decimal(interest),
            interest=Decimal(interest),
            method="pix",
            account=scenario["cash_register"],
            date=date,
        )


def pay_commission(scenario, practitioner, until=TODAY):
    return scenario["client"].post(
        f"{reverse('finance:commission_pay', args=[practitioner.pk])}?until={until.isoformat()}",
        {"due_date": TODAY.isoformat(), "category": scenario["category"].pk},
    )


def test_calculation_includes_interest_and_ignores_other_practitioners(scenario):
    receive(scenario, "100.00", scenario["dra"], interest="10.00")
    receive(scenario, "250.55", scenario["dra"])
    receive(scenario, "999.00", scenario["dr"])  # other practitioner
    receive(scenario, "500.00", None)  # no practitioner: no commission
    receive(scenario, "80.00", scenario["dra"], date=TODAY)  # after the cut-off date
    with use_clinic(scenario["clinic"]):
        calculation = commissions.pending(scenario["dra"], YESTERDAY)
    assert calculation["received_amount"] == Decimal("360.55")
    assert calculation["amount"] == Decimal("144.22")  # 40% of 360.55, rounded half up


def test_paying_creates_expense_and_never_pays_twice(scenario):
    receive(scenario, "300.00", scenario["dra"])
    response = pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        commission = Commission.objects.get()
        entry = commission.entry
        assert response.url == reverse("finance:entry", args=[entry.pk])
        assert (entry.kind, entry.total_amount, entry.payer) == (
            Entry.Kind.PAYABLE,
            Decimal("120.00"),
            "Dra. Ana",
        )
        assert entry.category.name == "Comissões"
        assert Payment.objects.get().commission == commission
        assert commissions.pending(scenario["dra"], TODAY)["amount"] == 0
    # Paying again finds nothing.
    pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        assert Commission.objects.count() == 1
    # Only new receipts make up the next one.
    receive(scenario, "50.00", scenario["dra"], date=TODAY)
    with use_clinic(scenario["clinic"]):
        assert commissions.pending(scenario["dra"], TODAY)["amount"] == Decimal("20.00")


def test_reversal_after_payment_is_deducted_from_the_next(scenario):
    payment = receive(scenario, "300.00", scenario["dra"])
    pay_commission(scenario, scenario["dra"])
    # The percentage changes, but the deduction uses the one it was paid with (40%).
    with use_clinic(scenario["clinic"]):
        Practitioner.objects.filter(pk=scenario["dra"].pk).update(commission_percentage=10)
        scenario["dra"].refresh_from_db()
        services.reverse_payment(payment, reason="Pix devolvido", user=scenario["admin"])
    receive(scenario, "1000.00", scenario["dra"], date=TODAY)
    with use_clinic(scenario["clinic"]):
        calculation = commissions.pending(scenario["dra"], TODAY)
        assert (calculation["gross"], calculation["reversal_deduction"], calculation["amount"]) == (
            Decimal("100.00"),
            Decimal("120.00"),
            Decimal("-20.00"),
        )
        # The list adds up in the database (volume test) and must agree with the detail.
        row = next(x for x in commissions.summary(TODAY) if x["practitioner"] == scenario["dra"])
        keys = ("received_amount", "gross", "reversal_deduction", "amount")
        assert [row[c] for c in keys] == [calculation[c] for c in keys]
    # Nothing to pay while the deduction is larger: it waits for more receipts.
    pay_commission(scenario, scenario["dra"])
    receive(scenario, "500.00", scenario["dra"], date=TODAY)
    pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        second = Commission.objects.latest("pk")
        assert (second.gross, second.reversal_deduction, second.amount) == (
            Decimal("150.00"),
            Decimal("120.00"),
            Decimal("30.00"),
        )
        payment.refresh_from_db()
        assert payment.commission_reversal == second
    statement = scenario["client"].get(reverse("finance:commission", args=[second.pk]))
    assert "Pix devolvido" not in statement.content.decode()  # reasons are not on the statement
    assert list(statement.context["reversal_deduction"]) == [payment]


def test_cancelling_the_expense_undoes_the_commission(scenario):
    receive(scenario, "300.00", scenario["dra"])
    pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        commission = Commission.objects.get()
    scenario["client"].post(
        reverse("finance:cancel", args=[commission.entry_id]), {"reason": "Errado"}
    )
    commission.refresh_from_db()
    assert commission.cancelled
    with use_clinic(scenario["clinic"]):
        assert not Payment.objects.filter(commission__isnull=False).exists()
        assert commissions.pending(scenario["dra"], TODAY)["amount"] == Decimal("120.00")


def test_screens_and_percentage(scenario):
    receive(scenario, "300.00", scenario["dra"])
    user_client = scenario["client"]
    page = user_client.get(reverse("finance:commissions"))
    assert [row["practitioner"] for row in page.context["rows"]] == [scenario["dra"]]
    assert list(page.context["without_percentage"]) == [scenario["dr"]]
    assert "R$ 120,00" in page.content.decode()
    url = reverse("finance:commission_percentage", args=[scenario["dr"].pk])
    assert user_client.post(url, {"commission_percentage": "101"}).status_code == 200  # > 100
    user_client.post(url, {"commission_percentage": "35,5"})
    scenario["dr"].refresh_from_db()
    assert scenario["dr"].commission_percentage == Decimal("35.50")
    pay = user_client.get(reverse("finance:commission_pay", args=[scenario["dra"].pk]))
    assert pay.context["calculation"]["amount"] == Decimal("120.00")
    # A future cut-off date is not allowed: it becomes today.
    future = (TODAY + datetime.timedelta(days=30)).isoformat()
    assert (
        user_client.get(reverse("finance:commissions"), {"until": future}).context["until"] == TODAY
    )


def test_only_the_admin(scenario):
    reception = scenario["client_for"](scenario["reception"])
    assert reception.get(reverse("finance:commissions")).status_code == 403
    assert (
        reception.post(reverse("finance:commission_pay", args=[scenario["dra"].pk])).status_code
        == 403
    )
    assert (
        reception.post(
            reverse("finance:commission_percentage", args=[scenario["dra"].pk]),
            {"commission_percentage": "90"},
        ).status_code
        == 403
    )


def test_practitioner_of_another_clinic_gives_404(scenario, clinic_b, create_user, client_for):
    other = client_for(create_user("admin_b", clinic_b, Role.ADMIN))
    assert (
        other.get(reverse("finance:commission_pay", args=[scenario["dra"].pk])).status_code == 404
    )


def test_does_not_cancel_commission_whose_reversal_was_deducted_elsewhere(scenario):
    """Cancelling C1 after C2 deducted a reversal of C1 would lose that amount for good."""
    payment = receive(scenario, "100.00", scenario["dra"])  # 40.00 in C1
    pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        first_one = Commission.objects.get()
        services.reverse_payment(payment, reason="Pix devolvido", user=scenario["admin"])
    receive(scenario, "300.00", scenario["dra"], date=TODAY)  # 120.00 - 40.00 in C2
    pay_commission(scenario, scenario["dra"])
    with use_clinic(scenario["clinic"]):
        second = Commission.objects.exclude(pk=first_one.pk).get()
    cancel = reverse("finance:cancel", args=[first_one.entry_id])
    response = scenario["client"].post(cancel, {"reason": "Errado"}, follow=True)
    assert "Cancele aquela antes" in response.content.decode()
    first_one.refresh_from_db()
    payment.refresh_from_db()
    assert not first_one.cancelled and not first_one.entry.cancelled
    assert (payment.commission, payment.commission_reversal) == (first_one, second)
    # In the right order both go, and everything is pending again.
    scenario["client"].post(reverse("finance:cancel", args=[second.entry_id]), {"reason": "Errado"})
    scenario["client"].post(cancel, {"reason": "Errado"})
    first_one.refresh_from_db()
    assert first_one.cancelled
    with use_clinic(scenario["clinic"]):
        assert commissions.pending(scenario["dra"], TODAY)["amount"] == Decimal("120.00")
