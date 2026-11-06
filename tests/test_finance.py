"""Receivables (0.15.0): installments, payments, receipts, debtors and permissions."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.urls import reverse
from django.utils import timezone, translation

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Role
from apps.finance import services
from apps.finance.models import Category, Entry, FinancialAccount, Installment, Payment
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture
def scenario(clinic_a, create_user, client_for):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Maria Devedora", tax_id="52998224725")
        category = Category.objects.get(name="Tratamento")
        cash_register = FinancialAccount.objects.get(name="Caixa")
    return {
        "clinic": clinic_a,
        "patient": patient,
        "category": category,
        "cash_register": cash_register,
        "admin": create_user("admin", clinic_a, Role.ADMIN),
        "reception": create_user("recepcao", clinic_a, Role.FRONT_DESK),
        "practitioner": create_user("dra", clinic_a, Role.PRACTITIONER),
        "client_for": client_for,
    }


def log_in(scenario, who):
    return scenario["client_for"](scenario[who])


def new(scenario, **extra):
    return {
        "patient": scenario["patient"].pk,
        "payer": "",
        "description": "Tratamento de canal",
        "category": scenario["category"].pk,
        "practitioner": "",
        "total_amount": "100,00",
        "installments": 3,
        "first_due_date": "2031-01-31",
        "notes": "",
        **extra,
    }


def entry_with(scenario, amount="300.00", installments=3, due_date=None, patient=True):
    with use_clinic(scenario["clinic"]):
        return services.create_entry(
            clinic=scenario["clinic"],
            kind=Entry.Kind.RECEIVABLE,
            patient=scenario["patient"] if patient else None,
            payer="" if patient else "João Avulso",
            description="Prótese",
            category=scenario["category"],
            total_amount=Decimal(amount),
            parcelas=installments,
            primeiro_vencimento=due_date or TODAY,
            user=scenario["admin"],
        )


def installments_of(scenario, entry):
    with use_clinic(scenario["clinic"]):
        return list(Installment.objects.with_balance().filter(entry=entry).order_by("number"))


# --- Rules -----------------------------------------------------------------------------


def test_split_into_installments_with_monthly_due_dates():
    assert services.split(Decimal("100.00"), 3) == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert services.add_months(datetime.date(2031, 1, 31), 1) == datetime.date(2031, 2, 28)
    assert services.add_months(datetime.date(2031, 11, 15), 3) == datetime.date(2032, 2, 15)


def test_new_clinic_gets_default_accounts_and_categories():
    clinic = Clinic.objects.create(name="Clínica Nova")
    with use_clinic(clinic):
        assert set(FinancialAccount.objects.values_list("name", flat=True)) == {"Caixa", "Banco"}
        assert Category.objects.filter(kind=Category.Kind.INCOME).count() == 3
        assert Category.objects.filter(kind=Category.Kind.EXPENSE).count() == 9


def test_currency_in_the_language_format():
    template_ = Template("{% load formats %}{{ amount|currency }}")
    with translation.override("pt-br"):
        assert template_.render(Context({"amount": Decimal("1234.5")})) == "R$ 1.234,50"
    with translation.override("en"):
        assert template_.render(Context({"amount": Decimal("1234.5")})) == "R$ 1,234.50"
    assert template_.render(Context({"amount": None})) == ""


# --- Entries and payments --------------------------------------------------------------


def test_reception_enters_installments(scenario):
    user_client = log_in(scenario, "reception")
    response = user_client.post(reverse("finance:entry_new"), new(scenario))
    assert response.status_code == 302
    with use_clinic(scenario["clinic"]):
        entry = Entry.objects.get()
        installments = list(entry.installments.order_by("number"))
    assert entry.created_by == scenario["reception"]
    assert [p.amount for p in installments] == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert [p.due_date for p in installments] == [
        datetime.date(2031, 1, 31),
        datetime.date(2031, 2, 28),
        datetime.date(2031, 3, 31),
    ]


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ({"patient": "", "payer": ""}, "payer"),
        ({"total_amount": "0"}, "total_amount"),
        ({"received_now": "on"}, "method"),
        ({"installments": 0}, "installments"),
    ],
)
def test_entry_validations(scenario, extra, field):
    response = log_in(scenario, "reception").post(
        reverse("finance:entry_new"), new(scenario, **extra)
    )
    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_immediate_payment_opens_the_receipt(scenario):
    user_client = log_in(scenario, "reception")
    response = user_client.post(
        reverse("finance:entry_new"),
        new(
            scenario,
            installments=1,
            total_amount="150,50",
            received_now="on",
            method=Payment.Method.PIX,
            account=scenario["cash_register"].pk,
        ),
        follow=True,
    )
    page = response.content.decode()
    assert "RECIBO" in page and "R$ 150,50" in page and "529.982.247-25" in page
    with use_clinic(scenario["clinic"]):
        assert Installment.objects.unpaid().count() == 0


def test_partial_payment_interest_and_balance(scenario):
    entry = entry_with(scenario)
    first_one = installments_of(scenario, entry)[0]
    user_client = log_in(scenario, "reception")
    url = reverse("finance:receive_installment", args=[first_one.pk])
    data = {
        "date": TODAY.isoformat(),
        "method": "dinheiro",
        "account": scenario["cash_register"].pk,
    }
    # 60 received, 10 of them late fee: the installment goes down by 50.
    assert user_client.post(url, {**data, "amount": "60", "interest": "10"}).status_code == 302
    first_one = installments_of(scenario, entry)[0]
    assert (first_one.paid, first_one.balance) == (Decimal("50.00"), Decimal("50.00"))
    assert services.status(first_one)[0] == "parcial"
    # Paying more than what is left is refused.
    response = user_client.post(url, {**data, "amount": "50,01"})
    assert "passa do que falta" in response.content.decode()
    user_client.post(url, {**data, "amount": "50"})
    assert installments_of(scenario, entry)[0].balance == 0


def test_discount_only_for_admin(scenario):
    entry = entry_with(scenario, amount="100.00", installments=1)
    installment = installments_of(scenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    data = {"date": TODAY.isoformat(), "method": "pix", "account": scenario["cash_register"].pk}

    reception = log_in(scenario, "reception")
    assert "discount" not in reception.get(url).context["form"].fields
    reception.post(url, {**data, "amount": "90", "discount": "10"})  # discount ignored
    assert installments_of(scenario, entry)[0].balance == Decimal("10.00")

    admin = log_in(scenario, "admin")
    admin.post(url, {**data, "amount": "5", "discount": "5"})
    assert installments_of(scenario, entry)[0].balance == 0


def test_reversal_and_cancellation_only_by_admin(scenario):
    entry = entry_with(scenario, amount="100.00", installments=1)
    installment = installments_of(scenario, entry)[0]
    with use_clinic(scenario["clinic"]):
        payment = services.receive(
            installment,
            user=scenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=scenario["cash_register"],
        )
    reception = log_in(scenario, "reception")
    reverse_payment = reverse("finance:reverse_payment", args=[payment.pk])
    cancel = reverse("finance:cancel", args=[entry.pk])
    assert reception.post(reverse_payment, {"reason": "x"}).status_code == 403
    assert reception.post(cancel, {"reason": "x"}).status_code == 403

    admin = log_in(scenario, "admin")
    # With an active payment the entry cannot be cancelled.
    response = admin.post(cancel, {"reason": "Desistiu"}, follow=True)
    assert "Estorne os pagamentos" in response.content.decode()
    # The page names the payment with the amount in reais (review stage 5: it read "100.00").
    assert "R$ 100,00" in admin.get(reverse_payment).content.decode()
    admin.post(reverse_payment, {"reason": "Pix devolvido"})
    payment.refresh_from_db()
    assert payment.reversed and payment.reversed_by == scenario["admin"]
    assert installments_of(scenario, entry)[0].balance == Decimal("100.00")
    assert "ESTORNADO" in admin.get(reverse("finance:receipt", args=[payment.pk])).content.decode()

    admin.post(cancel, {"reason": "Desistiu do tratamento"})
    entry.refresh_from_db()
    assert entry.cancelled and entry.cancellation_reason == "Desistiu do tratamento"
    # A second click (or a stale page) changes nothing.
    with use_clinic(scenario["clinic"]), pytest.raises(ValidationError):
        services.cancel(entry, reason="De novo", user=scenario["admin"])
    with use_clinic(scenario["clinic"]), pytest.raises(ValidationError):
        services.reverse_payment(payment, reason="De novo", user=scenario["admin"])
    entry.refresh_from_db()
    payment.refresh_from_db()
    assert entry.cancellation_reason == "Desistiu do tratamento"
    assert payment.reversal_reason == "Pix devolvido"
    with use_clinic(scenario["clinic"]):
        assert not Installment.objects.unpaid().exists()


def test_debtors_by_time_overdue(scenario):
    entry_with(
        scenario, amount="200.00", installments=2, due_date=TODAY - datetime.timedelta(days=45)
    )
    entry_with(
        scenario,
        amount="70.00",
        installments=1,
        due_date=TODAY - datetime.timedelta(days=100),
        patient=False,
    )
    with use_clinic(scenario["clinic"]):
        rows = services.debtors()
    assert [row["name"] for row in rows] == ["Maria Devedora", "João Avulso"]
    maria, joao = rows
    # 45 days late (31-60) and the next one 15 days late (up to 30).
    assert maria["brackets"] == [Decimal("100.00"), Decimal("100.00"), 0, 0]
    assert maria["overdue"] == Decimal("200.00")
    assert joao["brackets"][3] == Decimal("70.00")
    page = log_in(scenario, "reception").get(reverse("finance:debtors")).content.decode()
    assert "Maria Devedora" in page and "R$ 270,00" in page


def test_receivables_list_and_filters(scenario):
    entry_with(
        scenario, amount="90.00", installments=3, due_date=TODAY - datetime.timedelta(days=40)
    )
    user_client = log_in(scenario, "reception")
    results = reverse("finance:receivables")
    assert len(user_client.get(results).context["page"]) == 3
    assert len(user_client.get(results, {"status": "vencidas"}).context["page"]) == 2
    assert len(user_client.get(results, {"q": "devedora"}).context["page"]) == 3
    assert len(user_client.get(results, {"q": "ninguem"}).context["page"]) == 0


def test_record_shows_patient_finance(scenario):
    entry_with(
        scenario, amount="80.00", installments=2, due_date=TODAY - datetime.timedelta(days=5)
    )
    url = reverse("patients:record", args=[scenario["patient"].pk])
    response = log_in(scenario, "reception").get(url)
    finance_user = response.context["finance"]
    assert (finance_user["overdue"], finance_user["not_yet_due"]) == (
        Decimal("40.00"),
        Decimal("40.00"),
    )
    # Practitioners do not see the finances.
    assert "finance" not in log_in(scenario, "practitioner").get(url).context


# --- Permissions, isolation, records -----------------------------------------------------


def test_practitioner_cannot_access_finance(scenario):
    user_client = log_in(scenario, "practitioner")
    assert user_client.get(reverse("finance:receivables")).status_code == 403
    assert user_client.get(reverse("finance:debtors")).status_code == 403
    assert reverse("finance:receivables") not in user_client.get(reverse("home")).content.decode()


def test_reception_cannot_touch_categories_and_accounts(scenario):
    user_client = log_in(scenario, "reception")
    assert user_client.get(reverse("finance:catalog", args=["categories"])).status_code == 403
    assert user_client.get(reverse("finance:catalog_new", args=["accounts"])).status_code == 403


def test_admin_registers_categories_and_accounts(scenario):
    user_client = log_in(scenario, "admin")
    url = reverse("finance:catalog_new", args=["categories"])
    assert (
        user_client.post(url, {"name": "Ortodontia", "kind": "receita", "active": "on"}).status_code
        == 302
    )
    response = user_client.post(url, {"name": "Ortodontia", "kind": "receita", "active": "on"})
    assert "Já existe" in response.content.decode()
    user_client.post(
        reverse("finance:catalog_new", args=["accounts"]),
        {"name": "Maquininha", "kind": "cartao", "active": "on"},
    )
    with use_clinic(scenario["clinic"]):
        assert Category.objects.filter(name="Ortodontia").exists()
        assert FinancialAccount.objects.filter(name="Maquininha", kind="cartao").exists()
    assert user_client.get("/finance/something-else/").status_code == 404


def test_entry_of_another_clinic_gives_404(scenario, clinic_b, create_user, client_for):
    entry = entry_with(scenario)
    other = client_for(create_user("admin_b", clinic_b, Role.ADMIN))
    assert other.get(reverse("finance:entry", args=[entry.pk])).status_code == 404
    assert other.get(reverse("finance:receivables")).context["page"].paginator.count == 0


def test_permanent_deletion_keeps_entry_without_patient(scenario):
    entry = entry_with(scenario)
    with use_clinic(scenario["clinic"]):
        Entry.objects.filter(pk=entry.pk).update(notes="Mãe: Joana, 9999-0000")
        payment = services.receive(
            entry.installments.first(),
            user=scenario["admin"],
            amount=Decimal("10.00"),
            method="pix",
            account=FinancialAccount.objects.get(name="Caixa"),
            note="Pago pela Joana",
        )
        Patient.objects.filter(pk=scenario["patient"].pk).update(archived=True)
    admin = log_in(scenario, "admin")
    admin.post(reverse("patients:delete", args=[scenario["patient"].pk]))
    entry.refresh_from_db()
    payment.refresh_from_db()
    assert entry.patient is None
    assert entry.payer == f"Paciente excluído (código {scenario['patient'].pk})"
    # Notes may hold personal data; amounts stay.
    assert (entry.notes, payment.note) == ("", "")
    assert payment.amount == Decimal("10.00")


# --- Payables, cash flow and reports (0.16.0) ---------------------------------------------


def expense(scenario, **extra):
    with use_clinic(scenario["clinic"]):
        rent = Category.objects.get(name="Aluguel")
    return {
        "payer": "Imobiliária",
        "description": "Aluguel",
        "category": rent.pk,
        "amount": "3.000,00".replace(".", ""),
        "mode": "repetir",
        "installments": 12,
        "first_due_date": "2031-01-10",
        "notes": "",
        **extra,
    }


def test_fixed_monthly_and_installment_expense(scenario):
    admin = log_in(scenario, "admin")
    assert admin.post(reverse("finance:expense_new"), expense(scenario)).status_code == 302
    admin.post(
        reverse("finance:expense_new"),
        expense(scenario, description="Cadeira", mode="dividir", amount="900", installments=3),
    )
    with use_clinic(scenario["clinic"]):
        rent = Entry.objects.get(description="Aluguel")
        chair = Entry.objects.get(description="Cadeira")
        assert rent.kind == Entry.Kind.PAYABLE
        assert rent.total_amount == Decimal("36000.00")
        assert {p.amount for p in rent.installments.all()} == {Decimal("3000.00")}
        assert rent.installments.count() == 12
        assert [p.amount for p in chair.installments.order_by("number")] == [Decimal("300.00")] * 3


def test_expense_paid_at_once_and_installment_payment(scenario):
    admin = log_in(scenario, "admin")
    admin.post(
        reverse("finance:expense_new"),
        expense(
            scenario,
            installments=2,
            paid_now="on",
            method="pix",
            account=scenario["cash_register"].pk,
        ),
    )
    with use_clinic(scenario["clinic"]):
        entry = Entry.objects.get()
    second = installments_of(scenario, entry)[1]
    response = admin.post(
        reverse("finance:receive_installment", args=[second.pk]),
        {
            "date": TODAY.isoformat(),
            "amount": "3000",
            "method": "boleto",
            "account": scenario["cash_register"].pk,
        },
    )
    # Paying a bill goes back to the entry (receipts are only for money received).
    assert response.url == reverse("finance:entry", args=[entry.pk])
    assert all(p.balance == 0 for p in installments_of(scenario, entry))


def test_reception_does_not_see_payables(scenario):
    admin = log_in(scenario, "admin")
    admin.post(reverse("finance:expense_new"), expense(scenario, installments=1))
    with use_clinic(scenario["clinic"]):
        entry = Entry.objects.get()
        installment = entry.installments.get()
    reception = log_in(scenario, "reception")
    for url in (
        reverse("finance:payables"),
        reverse("finance:expense_new"),
        reverse("finance:cash_flow"),
        reverse("finance:reports"),
        reverse("finance:entry", args=[entry.pk]),
        reverse("finance:receive_installment", args=[installment.pk]),
    ):
        assert reception.get(url).status_code == 403, url
    assert reverse("finance:payables") not in reception.get(reverse("home")).content.decode()


def test_account_balance_with_opening_balance(scenario):
    with use_clinic(scenario["clinic"]):
        FinancialAccount.objects.filter(pk=scenario["cash_register"].pk).update(
            opening_balance=Decimal("-50.00")
        )
    entry = entry_with(scenario, amount="100.00", installments=1)
    with use_clinic(scenario["clinic"]):
        services.receive(
            installments_of(scenario, entry)[0],
            user=scenario["admin"],
            amount=Decimal("100"),
            method="dinheiro",
            account=scenario["cash_register"],
        )
        balances = dict((account.name, balance) for account, balance in services.account_balances())
    assert balances == {"Caixa": Decimal("50.00"), "Banco": Decimal("0.00")}
    # A negative initial balance is accepted in the form (overdrawn bank).
    admin = log_in(scenario, "admin")
    response = admin.post(
        reverse("finance:catalog_edit", args=["accounts", scenario["cash_register"].pk]),
        {"name": "Caixa", "kind": "dinheiro", "opening_balance": "-10,50", "active": "on"},
    )
    assert response.status_code == 302


def test_cash_flow_actual_and_forecast(scenario):
    since = datetime.date(2031, 3, 1)
    until = datetime.date(2031, 3, 31)
    receivable = entry_with(
        scenario, amount="200.00", installments=2, due_date=datetime.date(2031, 3, 5)
    )
    with use_clinic(scenario["clinic"]):
        FinancialAccount.objects.filter(pk=scenario["cash_register"].pk).update(
            opening_balance=Decimal("1000.00")
        )
        services.receive(
            installments_of(scenario, receivable)[0],
            user=scenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=scenario["cash_register"],
            date=datetime.date(2031, 3, 5),
        )
        rent = services.create_entry(
            clinic=scenario["clinic"],
            kind=Entry.Kind.PAYABLE,
            payer="Imobiliária",
            description="Aluguel",
            category=Category.objects.get(name="Aluguel"),
            total_amount=Decimal("300.00"),
            parcelas=1,
            primeiro_vencimento=datetime.date(2031, 3, 10),
            user=scenario["admin"],
        )
        flow = services.cash_flow(since, until, today=datetime.date(2031, 3, 1))
    assert flow["opening_balance"] == Decimal("1000.00")
    rows = {row["date"]: row for row in flow["rows"]}
    assert rows[datetime.date(2031, 3, 5)]["incoming"] == Decimal("100.00")
    assert rows[datetime.date(2031, 3, 10)]["expected_outgoing"] == Decimal("300.00")
    # 2nd receivable installment due 2031-04-05: outside the period.
    assert flow["closing_balance"] == Decimal("800.00")
    assert rent.total_amount == Decimal("300.00")
    response = log_in(scenario, "admin").get(
        reverse("finance:cash_flow"), {"since": "2031-03-01", "until": "2031-03-31", "group": "mes"}
    )
    assert response.status_code == 200 and response.context["by_month"]


def test_report_by_method_category_and_practitioner(scenario):
    entry = entry_with(scenario, amount="100.00", installments=1)
    with use_clinic(scenario["clinic"]):
        payment = services.receive(
            installments_of(scenario, entry)[0],
            user=scenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=scenario["cash_register"],
        )
        report = services.report(TODAY, TODAY)
    assert report["by_method"] == [("Pix", Decimal("100.00"))]
    assert report["by_category"] == [("Tratamento", Decimal("100.00"))]
    assert report["result"] == Decimal("100.00")
    # Reversed payments leave the reports.
    with use_clinic(scenario["clinic"]):
        services.reverse_payment(payment, reason="erro", user=scenario["admin"])
        assert services.report(TODAY, TODAY)["total_received"] == 0
    assert (
        log_in(scenario, "admin").get(reverse("finance:reports"), {"since": "lixo"}).status_code
        == 200
    )


def test_choice_lists_without_english_text(scenario):
    page = log_in(scenario, "admin").get(reverse("finance:expense_new")).content.decode()
    assert "Select an option" not in page


# --- Daily cash drawer (0.17.0) -----------------------------------------------------------


def test_full_daily_cash(scenario):
    from apps.finance.models import CashMovement, CashRegister

    with use_clinic(scenario["clinic"]):
        bank = FinancialAccount.objects.get(name="Banco")
    reception = log_in(scenario, "reception")
    assert reception.get(reverse("finance:cash")).status_code == 200
    response = reception.post(reverse("finance:cash"), {"amount": "100,00"})
    with use_clinic(scenario["clinic"]):
        cash_register = CashRegister.objects.get()
    assert response.url == reverse("finance:cash_detail", args=[cash_register.pk])
    # Only one open drawer per account: the page goes straight to it.
    assert reception.get(reverse("finance:cash")).url == response.url

    # A cash payment while the drawer is open enters it; a Pix into the bank does not.
    entry = entry_with(scenario, amount="80.00", installments=2)
    first_one, second = installments_of(scenario, entry)
    with use_clinic(scenario["clinic"]):
        services.receive(
            first_one,
            user=scenario["reception"],
            amount=Decimal("40"),
            method="dinheiro",
            account=scenario["cash_register"],
        )
        services.receive(
            second, user=scenario["reception"], amount=Decimal("40"), method="pix", account=bank
        )

    url = lambda name, *args: reverse(f"finance:{name}", args=[cash_register.pk, *args])  # noqa: E731
    reception.post(url("cash_movement", "top-up"), {"amount": "10", "reason": "Troco"})
    reception.post(
        url("cash_movement", "withdrawal"),
        {"amount": "120", "reason": "Depósito", "other_account": bank.pk},
    )
    # A withdrawal larger than what should be in the drawer is refused.
    response = reception.post(url("cash_movement", "withdrawal"), {"amount": "999", "reason": "x"})
    assert "passa do valor" in response.content.decode()

    with use_clinic(scenario["clinic"]):
        summary = services.register_summary(cash_register)
        balances = dict((c.name, s) for c, s in services.account_balances())
    assert (summary["incoming"], summary["top_ups"], summary["withdrawals"]) == (
        Decimal("40.00"),
        Decimal("10.00"),
        Decimal("120.00"),
    )
    assert summary["expected"] == Decimal("30.00")  # 100 + 40 + 10 - 120
    # The deposit moved money from the drawer account to the bank.
    assert balances == {"Caixa": Decimal("-70.00"), "Banco": Decimal("160.00")}

    reception.post(url("cash_close"), {"counted_amount": "28,50", "note": "Faltou troco"})
    cash_register.refresh_from_db()
    assert not cash_register.is_open and cash_register.closed_by == scenario["reception"]
    assert (
        cash_register.expected_amount,
        cash_register.counted_amount,
        cash_register.difference,
    ) == (
        Decimal("30.00"),
        Decimal("28.50"),
        Decimal("-1.50"),
    )
    # Closed: no more movements, and a new drawer can be opened.
    assert reception.get(url("cash_close")).status_code == 404
    assert reception.get(url("cash_movement", "other")).status_code == 404
    reception.post(reverse("finance:cash"), {"amount": "28,50"})
    with use_clinic(scenario["clinic"]):
        assert CashRegister.objects.filter(closed_at__isnull=True).count() == 1
        assert CashMovement.objects.count() == 2


def test_practitioner_does_not_operate_cash(scenario):
    assert log_in(scenario, "practitioner").get(reverse("finance:cash")).status_code == 403


def test_closed_cash_does_not_change_with_later_reversal(scenario):
    with use_clinic(scenario["clinic"]):
        cash_register = services.open_register(
            scenario["cash_register"], amount=Decimal("0"), user=scenario["admin"]
        )
    entry = entry_with(scenario, amount="50.00", installments=1)
    with use_clinic(scenario["clinic"]):
        payment = services.receive(
            installments_of(scenario, entry)[0],
            user=scenario["admin"],
            amount=Decimal("50"),
            method="dinheiro",
            account=scenario["cash_register"],
        )
        services.close_register(
            cash_register, counted_amount=Decimal("50"), note="", user=scenario["admin"]
        )
        services.reverse_payment(payment, reason="erro", user=scenario["admin"])
        cash_register.refresh_from_db()
    assert (cash_register.expected_amount, cash_register.difference) == (Decimal("50.00"), 0)


@pytest.mark.parametrize("typed", ["1.500,00", "R$ 1.500,00", "1500,00", "1.500"])
def test_amount_with_thousands_dot(scenario, typed):
    """Review stage 3: "1.500,00", as people write it, was refused ("Informe um número")."""
    response = log_in(scenario, "admin").post(
        reverse("finance:entry_new"), new(scenario, total_amount=typed, installments=1)
    )
    assert response.status_code == 302, response.context["form"].errors
    with use_clinic(scenario["clinic"]):
        assert Entry.objects.get().total_amount == Decimal("1500.00")


def test_check_is_no_longer_offered(scenario):
    """The owner: cheques are not used anymore. A cheque recorded before keeps its name."""
    entry = entry_with(scenario)
    installment = installments_of(scenario, entry)[0]
    admin = log_in(scenario, "admin")
    for url in (
        reverse("finance:receive_installment", args=[installment.pk]),
        reverse("finance:entry_new"),
        reverse("finance:expense_new"),
    ):
        page = admin.get(url).content.decode()
        assert 'value="pix"' in page and 'value="cheque"' not in page, url
    refused_one = admin.post(
        reverse("finance:receive_installment", args=[installment.pk]),
        {
            "date": "2026-10-30",
            "amount": "100,00",
            "method": "cheque",
            "account": scenario["cash_register"].pk,
        },
    )
    assert "method" in refused_one.context["form"].errors
    with use_clinic(scenario["clinic"]):
        old = services.receive(
            installment,
            user=scenario["admin"],
            amount=Decimal("100"),
            method="cheque",
            account=scenario["cash_register"],
        )
    assert old.get_method_display() == "Cheque"


def test_debtors_paginated_and_searchable(scenario):
    """Volume test: thousands of debtors filled a single page of several MB."""
    with use_clinic(scenario["clinic"]):
        for n in range(55):
            services.create_entry(
                clinic=scenario["clinic"],
                kind=Entry.Kind.RECEIVABLE,
                payer=f"Pagador Fictício {n:02d}",
                description="Consulta",
                category=scenario["category"],
                total_amount=Decimal("10"),
                parcelas=1,
                primeiro_vencimento=TODAY - datetime.timedelta(days=10),
                user=scenario["admin"],
            )
    user_client = log_in(scenario, "reception")
    first_one = user_client.get(reverse("finance:debtors")).content.decode()
    assert "55 devedores" in first_one and "Página 1 de 2" in first_one
    assert "R$ 550,00" in first_one  # the totals still add up everyone
    search = user_client.get(reverse("finance:debtors"), {"q": "fictício 07"}).content.decode()
    assert "Pagador Fictício 07" in search and "Pagador Fictício 08" not in search
