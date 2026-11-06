"""Yearly planning (decision 098): goals per group next to what was paid. Fictitious data."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance import services
from apps.finance.models import AccountGroup, Category, Entry, FinancialAccount, Planning

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()
URL = reverse("finance:planning")


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_planejamento", clinic_a, Role.ADMIN))


def group(clinic, name):
    with use_clinic(clinic):
        return AccountGroup.objects.get(name=name)


def pay(clinic, category, amount, date=TODAY):
    with use_clinic(clinic):
        entry = services.create_entry(
            clinic=clinic,
            kind=Entry.Kind.PAYABLE,
            payer="Fictício",
            description="Despesa",
            category=Category.objects.get(name=category),
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=None,
        )
        installment = entry.parcelas.get()
        services.receive(
            installment,
            user=None,
            amount=installment.amount,
            date=date,
            method="pix",
            account=FinancialAccount.objects.get(name="Caixa"),
        )


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (datetime.date(2025, 12, 31), Decimal(0)),
        (datetime.date(2027, 1, 1), Decimal(1)),
        (datetime.date(2026, 1, 1), Decimal(1) / Decimal(365)),
    ],
)
def test_fraction_of_the_year(today, expected):
    assert services.year_fraction(2026, today) == expected


def test_save_targets_in_brazilian_format(clinic_a, admin):
    occupation = group(clinic_a, "Ocupação")
    # With the thousands dot, as people type it (review stage 3: it was refused).
    response = admin.post(f"{URL}?year={TODAY.year}", {f"meta-{occupation.pk}": "12.000,50"})
    assert response.status_code == 302
    with use_clinic(clinic_a):
        assert Planning.objects.get().amount == Decimal("12000.50")
    page = admin.get(f"{URL}?year={TODAY.year}").content.decode()
    assert 'value="12000,50"' in page  # shown back with a comma, not as 12000.50
    # Blank removes the goal.
    admin.post(f"{URL}?year={TODAY.year}", {f"meta-{occupation.pk}": ""})
    with use_clinic(clinic_a):
        assert not Planning.objects.exists()


def test_actual_and_percentage_summing_subgroups(clinic_a, admin):
    with use_clinic(clinic_a):
        occupation = AccountGroup.objects.get(name="Ocupação")
        Planning.objects.create(year=TODAY.year, group=occupation, amount=Decimal("1000"))
    pay(clinic_a, "Aluguel", "250")
    pay(clinic_a, "Manutenção", "50")
    pay(clinic_a, "Aluguel", "999", date=datetime.date(TODAY.year - 1, 6, 1))  # other year
    expenses = admin.get(f"{URL}?year={TODAY.year}").context["sections"][1]
    row = next(row for row in expenses["rows"] if row["group"] == occupation)
    assert (row["actual"], row["percentage"]) == (Decimal("300.00"), 30)
    assert expenses["target"] == Decimal("1000") and expenses["actual"] == Decimal("300.00")


def test_subgroup_target_does_not_count_twice(clinic_a):
    with use_clinic(clinic_a):
        staff_ = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", parent=staff_)
        Planning.objects.create(year=2026, group=staff_, amount=Decimal("5000"))
        Planning.objects.create(year=2026, group=sub, amount=Decimal("2000"))
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("700")
        )
        expenses = services.planning(2026, today=datetime.date(2026, 12, 31))["sections"][1]
    assert expenses["target"] == Decimal("5700")
    assert expenses["expected"] == Decimal("5700.00")


def test_on_track_for_revenue_and_expense(clinic_a):
    with use_clinic(clinic_a):
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Atendimentos"), amount=Decimal("1200")
        )
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("1200")
        )
        data = services.planning(2026, today=datetime.date(2026, 12, 31))
    income = next(row for row in data["sections"][0]["rows"] if row["target"])
    expense = next(row for row in data["sections"][1]["rows"] if row["target"])
    # Nothing received yet: income is behind; nothing paid: expenses are within the goal.
    assert income["on_track"] is False and expense["on_track"] is True


def test_copy_targets_from_previous_year(clinic_a, admin):
    with use_clinic(clinic_a):
        occupation = AccountGroup.objects.get(name="Ocupação")
        taxes = AccountGroup.objects.get(name="Impostos")
        Planning.objects.create(year=TODAY.year - 1, group=occupation, amount=Decimal("900"))
        Planning.objects.create(year=TODAY.year - 1, group=taxes, amount=Decimal("300"))
        Planning.objects.create(year=TODAY.year, group=taxes, amount=Decimal("400"))
    page = admin.get(f"{URL}?year={TODAY.year}")
    assert page.context["has_previous_targets"]
    admin.post(f"{URL}?year={TODAY.year}", {"action": "copiar"})
    with use_clinic(clinic_a):
        this_year = dict(
            Planning.objects.filter(year=TODAY.year).values_list("group__name", "amount")
        )
    assert this_year == {"Ocupação": Decimal("900.00"), "Impostos": Decimal("400.00")}


def test_invalid_year_falls_back_to_current(admin):
    assert admin.get(URL, {"year": "abc"}).context["year"] == TODAY.year


def test_permissions(clinic_a, create_user, client_for):
    reception = client_for(create_user("recepcao_planejamento", clinic_a, Role.FRONT_DESK))
    assert reception.get(URL).status_code == 403
