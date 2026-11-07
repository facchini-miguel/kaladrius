"""Cost centers (decision 095): register, optional on entries, reports. Fictitious data only."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import GENERAL_MODULES, ModuleCode, Role
from apps.core.modules import configure
from apps.finance import services
from apps.finance.models import Category, CostCenter, Entry, FinancialAccount
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()
URL = "finance:catalog"


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_centros", clinic_a, Role.ADMIN))


@pytest.fixture
def center(clinic_a):
    with use_clinic(clinic_a):
        return CostCenter.objects.create(name="Ortodontia")


def expense(clinic, **extra):
    with use_clinic(clinic):
        category = Category.objects.get(name="Aluguel")
    return {
        "payer": "Imobiliária fictícia",
        "description": "Aluguel",
        "category": category.pk,
        "amount": "1000",
        "mode": "split",
        "installments": 1,
        "first_due_date": TODAY.isoformat(),
        "notes": "",
        **extra,
    }


def test_registration_and_duplicate_name(clinic_a, admin):
    url = reverse("finance:catalog_new", args=["cost-centers"])
    assert admin.post(url, {"name": " Consultório 1 ", "active": "on"}).status_code == 302
    with use_clinic(clinic_a):
        assert CostCenter.objects.get().name == "Consultório 1"
    repeated_one = admin.post(url, {"name": "consultório 1", "active": "on"})
    assert "name" in repeated_one.context["form"].errors
    results = admin.get(reverse(URL, args=["cost-centers"])).content.decode()
    assert "Consultório 1" in results and "Ativo" in results


def test_field_shows_only_with_a_registered_center(clinic_a, admin):
    for route in ("finance:entry_new", "finance:expense_new"):
        assert "cost_center" not in admin.get(reverse(route)).context["form"].fields
    with use_clinic(clinic_a):
        inactive = CostCenter.objects.create(name="Desativado", active=False)
    assert "cost_center" not in admin.get(reverse("finance:expense_new")).context["form"].fields
    with use_clinic(clinic_a):
        CostCenter.objects.create(name="Ativo")
    field = admin.get(reverse("finance:expense_new")).context["form"].fields["cost_center"]
    with use_clinic(clinic_a):
        assert inactive not in field.queryset and field.queryset.count() == 1


def test_entries_keep_the_center(clinic_a, center, admin):
    assert (
        admin.post(
            reverse("finance:expense_new"), expense(clinic_a, cost_center=center.pk)
        ).status_code
        == 302
    )
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paciente fictício do centro")
        income = Category.objects.get(name="Tratamento")
    response = admin.post(
        reverse("finance:entry_new"),
        {
            "patient": patient.pk,
            "payer": "",
            "description": "Aparelho",
            "category": income.pk,
            "cost_center": center.pk,
            "practitioner": "",
            "total_amount": "500",
            "installments": 1,
            "first_due_date": TODAY.isoformat(),
            "notes": "",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        assert Entry.objects.filter(cost_center=center).count() == 2
        entry = Entry.objects.get(kind=Entry.Kind.PAYABLE)
    page = admin.get(reverse("finance:entry", args=[entry.pk])).content.decode()
    assert "Ortodontia" in page
    # Without a center the entry still saves (the field is optional).
    assert admin.post(reverse("finance:expense_new"), expense(clinic_a)).status_code == 302


def test_report_by_cost_center(clinic_a, center, admin):
    with use_clinic(clinic_a):
        rent = Category.objects.get(name="Aluguel")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        for amount, cost_center in ((Decimal("300"), center), (Decimal("200"), None)):
            entry = services.create_entry(
                clinic=clinic_a,
                kind=Entry.Kind.PAYABLE,
                payer="Fornecedor fictício",
                description="Compra",
                category=rent,
                cost_center=cost_center,
                total_amount=amount,
                installments=1,
                first_due_date=TODAY,
                user=None,
            )
            installment = entry.installments.get()
            services.receive(
                installment,
                user=None,
                amount=installment.amount,
                method="pix",
                account=cash_register,
            )
    report = admin.get(reverse("finance:reports")).context["report"]
    assert report["centers"]
    assert {name: str(total) for name, total in report["expenses_by_center"]} == {
        "Ortodontia": "300.00",
        "Sem centro de custo": "200.00",
    }
    assert (
        "Despesas pagas por centro de custo"
        in admin.get(reverse("finance:reports")).content.decode()
    )


def test_report_without_centers_hides_the_tables(admin):
    report = admin.get(reverse("finance:reports"))
    assert not report.context["report"]["centers"]
    assert "por centro de custo" not in report.content.decode()


def test_reception_does_not_register(clinic_a, create_user, client_for):
    reception = client_for(create_user("recepcao_centros", clinic_a, Role.FRONT_DESK))
    assert reception.get(reverse(URL, args=["cost-centers"])).status_code == 403


def test_hidden_with_finance_off(clinic_a, admin):
    results = reverse(URL, args=["cost-centers"])
    assert results in admin.get(reverse("home")).content.decode()
    configure(
        clinic_a,
        GENERAL_MODULES - {ModuleCode.FINANCE, ModuleCode.ESTIMATES, ModuleCode.STAFF},
    )
    assert admin.get(results).status_code == 403
    assert results not in admin.get(reverse("home")).content.decode()
