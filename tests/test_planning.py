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

HOJE = timezone.localdate()
URL = reverse("finance:planning")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_planejamento", clinica_a, Role.ADMIN))


def group(clinic, name):
    with use_clinic(clinic):
        return AccountGroup.objects.get(name=name)


def pay(clinic, category, amount, date=HOJE):
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
    ("today", "esperado"),
    [
        (datetime.date(2025, 12, 31), Decimal(0)),
        (datetime.date(2027, 1, 1), Decimal(1)),
        (datetime.date(2026, 1, 1), Decimal(1) / Decimal(365)),
    ],
)
def test_fraction_of_the_year(today, esperado):
    assert services.year_fraction(2026, today) == esperado


def test_save_targets_in_brazilian_format(clinica_a, admin):
    ocupacao = group(clinica_a, "Ocupação")
    # With the thousands dot, as people type it (review stage 3: it was refused).
    response = admin.post(f"{URL}?year={HOJE.year}", {f"meta-{ocupacao.pk}": "12.000,50"})
    assert response.status_code == 302
    with use_clinic(clinica_a):
        assert Planning.objects.get().amount == Decimal("12000.50")
    page = admin.get(f"{URL}?year={HOJE.year}").content.decode()
    assert 'value="12000,50"' in page  # shown back with a comma, not as 12000.50
    # Blank removes the goal.
    admin.post(f"{URL}?year={HOJE.year}", {f"meta-{ocupacao.pk}": ""})
    with use_clinic(clinica_a):
        assert not Planning.objects.exists()


def test_actual_and_percentage_summing_subgroups(clinica_a, admin):
    with use_clinic(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        Planning.objects.create(year=HOJE.year, group=ocupacao, amount=Decimal("1000"))
    pay(clinica_a, "Aluguel", "250")
    pay(clinica_a, "Manutenção", "50")
    pay(clinica_a, "Aluguel", "999", date=datetime.date(HOJE.year - 1, 6, 1))  # other year
    despesas = admin.get(f"{URL}?year={HOJE.year}").context["sections"][1]
    row = next(row for row in despesas["linhas"] if row["group"] == ocupacao)
    assert (row["realizado"], row["percentage"]) == (Decimal("300.00"), 30)
    assert despesas["meta"] == Decimal("1000") and despesas["realizado"] == Decimal("300.00")


def test_subgroup_target_does_not_count_twice(clinica_a):
    with use_clinic(clinica_a):
        pessoal = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", parent=pessoal)
        Planning.objects.create(year=2026, group=pessoal, amount=Decimal("5000"))
        Planning.objects.create(year=2026, group=sub, amount=Decimal("2000"))
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("700")
        )
        despesas = services.planning(2026, today=datetime.date(2026, 12, 31))["sections"][1]
    assert despesas["meta"] == Decimal("5700")
    assert despesas["esperado"] == Decimal("5700.00")


def test_on_track_for_revenue_and_expense(clinica_a):
    with use_clinic(clinica_a):
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Atendimentos"), amount=Decimal("1200")
        )
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("1200")
        )
        data = services.planning(2026, today=datetime.date(2026, 12, 31))
    receita = next(row for row in data["sections"][0]["linhas"] if row["meta"])
    despesa = next(row for row in data["sections"][1]["linhas"] if row["meta"])
    # Nothing received yet: income is behind; nothing paid: expenses are within the goal.
    assert receita["em_dia"] is False and despesa["em_dia"] is True


def test_copy_targets_from_previous_year(clinica_a, admin):
    with use_clinic(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        impostos = AccountGroup.objects.get(name="Impostos")
        Planning.objects.create(year=HOJE.year - 1, group=ocupacao, amount=Decimal("900"))
        Planning.objects.create(year=HOJE.year - 1, group=impostos, amount=Decimal("300"))
        Planning.objects.create(year=HOJE.year, group=impostos, amount=Decimal("400"))
    page = admin.get(f"{URL}?year={HOJE.year}")
    assert page.context["has_previous_targets"]
    admin.post(f"{URL}?year={HOJE.year}", {"action": "copiar"})
    with use_clinic(clinica_a):
        deste_ano = dict(
            Planning.objects.filter(year=HOJE.year).values_list("group__name", "amount")
        )
    assert deste_ano == {"Ocupação": Decimal("900.00"), "Impostos": Decimal("400.00")}


def test_invalid_year_falls_back_to_current(admin):
    assert admin.get(URL, {"year": "abc"}).context["year"] == HOJE.year


def test_permissions(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_planejamento", clinica_a, Role.FRONT_DESK))
    assert reception.get(URL).status_code == 403
