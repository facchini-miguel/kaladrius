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
HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    admin = criar_usuario("admin", clinica_a, Role.ADMIN)
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Paulo Paciente")
        dra = Practitioner.objects.create(name="Dra. Ana", commission_percentage=Decimal("40"))
        dr = Practitioner.objects.create(name="Dr. Beto")
        tratamento = Category.objects.get(name="Tratamento")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        category = Category.objects.get(name="Comissões")
    return {
        "clinic": clinica_a,
        "patient": patient,
        "dra": dra,
        "dr": dr,
        "tratamento": tratamento,
        "cash_register": cash_register,
        "category": category,
        "admin": admin,
        "recepcao": criar_usuario("recepcao", clinica_a, Role.FRONT_DESK),
        # The test client is shared: log in as the administrator by default.
        "cliente": cliente_de(admin),
        "cliente_de": cliente_de,
    }


def receive(cenario, amount, practitioner, date=ONTEM, interest="0"):
    """A receivable for `valor` paid in full on `data`."""
    with use_clinic(cenario["clinic"]):
        entry = services.create_entry(
            clinic=cenario["clinic"],
            kind=Entry.Kind.RECEIVABLE,
            patient=cenario["patient"],
            practitioner=practitioner,
            description="Tratamento",
            category=cenario["tratamento"],
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=cenario["admin"],
        )
        return services.receive(
            entry.parcelas.get(),
            user=cenario["admin"],
            amount=Decimal(amount) + Decimal(interest),
            interest=Decimal(interest),
            method="pix",
            account=cenario["cash_register"],
            date=date,
        )


def pagar_comissao(cenario, practitioner, until=HOJE):
    return cenario["cliente"].post(
        f"{reverse('finance:commission_pay', args=[practitioner.pk])}?until={until.isoformat()}",
        {"due_date": HOJE.isoformat(), "category": cenario["category"].pk},
    )


def test_calculation_includes_interest_and_ignores_other_practitioners(cenario):
    receive(cenario, "100.00", cenario["dra"], interest="10.00")
    receive(cenario, "250.55", cenario["dra"])
    receive(cenario, "999.00", cenario["dr"])  # other practitioner
    receive(cenario, "500.00", None)  # no practitioner: no commission
    receive(cenario, "80.00", cenario["dra"], date=HOJE)  # after the cut-off date
    with use_clinic(cenario["clinic"]):
        calculo = commissions.pending(cenario["dra"], ONTEM)
    assert calculo["received_amount"] == Decimal("360.55")
    assert calculo["amount"] == Decimal("144.22")  # 40% of 360.55, rounded half up


def test_paying_creates_expense_and_never_pays_twice(cenario):
    receive(cenario, "300.00", cenario["dra"])
    response = pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
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
        assert commissions.pending(cenario["dra"], HOJE)["amount"] == 0
    # Paying again finds nothing.
    pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
        assert Commission.objects.count() == 1
    # Only new receipts make up the next one.
    receive(cenario, "50.00", cenario["dra"], date=HOJE)
    with use_clinic(cenario["clinic"]):
        assert commissions.pending(cenario["dra"], HOJE)["amount"] == Decimal("20.00")


def test_reversal_after_payment_is_deducted_from_the_next(cenario):
    payment = receive(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    # The percentage changes, but the deduction uses the one it was paid with (40%).
    with use_clinic(cenario["clinic"]):
        Practitioner.objects.filter(pk=cenario["dra"].pk).update(commission_percentage=10)
        cenario["dra"].refresh_from_db()
        services.reverse_payment(payment, reason="Pix devolvido", user=cenario["admin"])
    receive(cenario, "1000.00", cenario["dra"], date=HOJE)
    with use_clinic(cenario["clinic"]):
        calculo = commissions.pending(cenario["dra"], HOJE)
        assert (calculo["gross"], calculo["reversal_deduction"], calculo["amount"]) == (
            Decimal("100.00"),
            Decimal("120.00"),
            Decimal("-20.00"),
        )
        # The list adds up in the database (volume test) and must agree with the detail.
        row = next(x for x in commissions.summary(HOJE) if x["practitioner"] == cenario["dra"])
        chaves = ("received_amount", "gross", "reversal_deduction", "amount")
        assert [row[c] for c in chaves] == [calculo[c] for c in chaves]
    # Nothing to pay while the deduction is larger: it waits for more receipts.
    pagar_comissao(cenario, cenario["dra"])
    receive(cenario, "500.00", cenario["dra"], date=HOJE)
    pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
        segunda = Commission.objects.latest("pk")
        assert (segunda.gross, segunda.reversal_deduction, segunda.amount) == (
            Decimal("150.00"),
            Decimal("120.00"),
            Decimal("30.00"),
        )
        payment.refresh_from_db()
        assert payment.commission_reversal == segunda
    statement = cenario["cliente"].get(reverse("finance:commission", args=[segunda.pk]))
    assert "Pix devolvido" not in statement.content.decode()  # reasons are not on the statement
    assert list(statement.context["reversal_deduction"]) == [payment]


def test_cancelling_the_expense_undoes_the_commission(cenario):
    receive(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
        commission = Commission.objects.get()
    cenario["cliente"].post(
        reverse("finance:cancel", args=[commission.entry_id]), {"reason": "Errado"}
    )
    commission.refresh_from_db()
    assert commission.cancelled
    with use_clinic(cenario["clinic"]):
        assert not Payment.objects.filter(commission__isnull=False).exists()
        assert commissions.pending(cenario["dra"], HOJE)["amount"] == Decimal("120.00")


def test_screens_and_percentage(cenario):
    receive(cenario, "300.00", cenario["dra"])
    cliente = cenario["cliente"]
    page = cliente.get(reverse("finance:commissions"))
    assert [row["practitioner"] for row in page.context["rows"]] == [cenario["dra"]]
    assert list(page.context["without_percentage"]) == [cenario["dr"]]
    assert "R$ 120,00" in page.content.decode()
    url = reverse("finance:commission_percentage", args=[cenario["dr"].pk])
    assert cliente.post(url, {"commission_percentage": "101"}).status_code == 200  # > 100
    cliente.post(url, {"commission_percentage": "35,5"})
    cenario["dr"].refresh_from_db()
    assert cenario["dr"].commission_percentage == Decimal("35.50")
    pay = cliente.get(reverse("finance:commission_pay", args=[cenario["dra"].pk]))
    assert pay.context["calculation"]["amount"] == Decimal("120.00")
    # A future cut-off date is not allowed: it becomes today.
    futuro = (HOJE + datetime.timedelta(days=30)).isoformat()
    assert cliente.get(reverse("finance:commissions"), {"until": futuro}).context["until"] == HOJE


def test_only_the_admin(cenario):
    reception = cenario["cliente_de"](cenario["recepcao"])
    assert reception.get(reverse("finance:commissions")).status_code == 403
    assert (
        reception.post(reverse("finance:commission_pay", args=[cenario["dra"].pk])).status_code
        == 403
    )
    assert (
        reception.post(
            reverse("finance:commission_percentage", args=[cenario["dra"].pk]),
            {"commission_percentage": "90"},
        ).status_code
        == 403
    )


def test_practitioner_of_another_clinic_gives_404(cenario, clinica_b, criar_usuario, cliente_de):
    other = cliente_de(criar_usuario("admin_b", clinica_b, Role.ADMIN))
    assert other.get(reverse("finance:commission_pay", args=[cenario["dra"].pk])).status_code == 404


def test_does_not_cancel_commission_whose_reversal_was_deducted_elsewhere(cenario):
    """Cancelling C1 after C2 deducted a reversal of C1 would lose that amount for good."""
    payment = receive(cenario, "100.00", cenario["dra"])  # 40.00 in C1
    pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
        primeira = Commission.objects.get()
        services.reverse_payment(payment, reason="Pix devolvido", user=cenario["admin"])
    receive(cenario, "300.00", cenario["dra"], date=HOJE)  # 120.00 - 40.00 in C2
    pagar_comissao(cenario, cenario["dra"])
    with use_clinic(cenario["clinic"]):
        segunda = Commission.objects.exclude(pk=primeira.pk).get()
    cancel = reverse("finance:cancel", args=[primeira.entry_id])
    response = cenario["cliente"].post(cancel, {"reason": "Errado"}, follow=True)
    assert "Cancele aquela antes" in response.content.decode()
    primeira.refresh_from_db()
    payment.refresh_from_db()
    assert not primeira.cancelled and not primeira.entry.cancelled
    assert (payment.commission, payment.commission_reversal) == (primeira, segunda)
    # In the right order both go, and everything is pending again.
    cenario["cliente"].post(
        reverse("finance:cancel", args=[segunda.entry_id]), {"reason": "Errado"}
    )
    cenario["cliente"].post(cancel, {"reason": "Errado"})
    primeira.refresh_from_db()
    assert primeira.cancelled
    with use_clinic(cenario["clinic"]):
        assert commissions.pending(cenario["dra"], HOJE)["amount"] == Decimal("120.00")
