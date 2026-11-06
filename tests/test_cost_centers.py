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

HOJE = timezone.localdate()
URL = "finance:catalog"


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_centros", clinica_a, Role.ADMIN))


@pytest.fixture
def centro(clinica_a):
    with use_clinic(clinica_a):
        return CostCenter.objects.create(name="Ortodontia")


def despesa(clinic, **extra):
    with use_clinic(clinic):
        category = Category.objects.get(name="Aluguel")
    return {
        "payer": "Imobiliária fictícia",
        "description": "Aluguel",
        "category": category.pk,
        "amount": "1000",
        "mode": "dividir",
        "installments": 1,
        "first_due_date": HOJE.isoformat(),
        "notes": "",
        **extra,
    }


def test_registration_and_duplicate_name(clinica_a, admin):
    url = reverse("finance:catalog_new", args=["cost-centers"])
    assert admin.post(url, {"name": " Consultório 1 ", "active": "on"}).status_code == 302
    with use_clinic(clinica_a):
        assert CostCenter.objects.get().name == "Consultório 1"
    repetido = admin.post(url, {"name": "consultório 1", "active": "on"})
    assert "name" in repetido.context["form"].errors
    results = admin.get(reverse(URL, args=["cost-centers"])).content.decode()
    assert "Consultório 1" in results and "Ativo" in results


def test_field_shows_only_with_a_registered_center(clinica_a, admin):
    for rota in ("finance:entry_new", "finance:expense_new"):
        assert "cost_center" not in admin.get(reverse(rota)).context["form"].fields
    with use_clinic(clinica_a):
        inativo = CostCenter.objects.create(name="Desativado", active=False)
    assert "cost_center" not in admin.get(reverse("finance:expense_new")).context["form"].fields
    with use_clinic(clinica_a):
        CostCenter.objects.create(name="Ativo")
    field = admin.get(reverse("finance:expense_new")).context["form"].fields["cost_center"]
    with use_clinic(clinica_a):
        assert inativo not in field.queryset and field.queryset.count() == 1


def test_entries_keep_the_center(clinica_a, centro, admin):
    assert (
        admin.post(
            reverse("finance:expense_new"), despesa(clinica_a, cost_center=centro.pk)
        ).status_code
        == 302
    )
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Paciente fictício do centro")
        receita = Category.objects.get(name="Tratamento")
    response = admin.post(
        reverse("finance:entry_new"),
        {
            "patient": patient.pk,
            "payer": "",
            "description": "Aparelho",
            "category": receita.pk,
            "cost_center": centro.pk,
            "practitioner": "",
            "total_amount": "500",
            "installments": 1,
            "first_due_date": HOJE.isoformat(),
            "notes": "",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        assert Entry.objects.filter(cost_center=centro).count() == 2
        entry = Entry.objects.get(kind=Entry.Kind.PAYABLE)
    page = admin.get(reverse("finance:entry", args=[entry.pk])).content.decode()
    assert "Ortodontia" in page
    # Without a center the entry still saves (the field is optional).
    assert admin.post(reverse("finance:expense_new"), despesa(clinica_a)).status_code == 302


def test_report_by_cost_center(clinica_a, centro, admin):
    with use_clinic(clinica_a):
        aluguel = Category.objects.get(name="Aluguel")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        for amount, cost_center in ((Decimal("300"), centro), (Decimal("200"), None)):
            entry = services.create_entry(
                clinic=clinica_a,
                kind=Entry.Kind.PAYABLE,
                payer="Fornecedor fictício",
                description="Compra",
                category=aluguel,
                cost_center=cost_center,
                total_amount=amount,
                parcelas=1,
                primeiro_vencimento=HOJE,
                user=None,
            )
            installment = entry.parcelas.get()
            services.receive(
                installment,
                user=None,
                amount=installment.amount,
                method="pix",
                account=cash_register,
            )
    report = admin.get(reverse("finance:reports")).context["report"]
    assert report["centros"]
    assert {name: str(total) for name, total in report["despesas_por_centro"]} == {
        "Ortodontia": "300.00",
        "Sem centro de custo": "200.00",
    }
    assert (
        "Despesas pagas por centro de custo"
        in admin.get(reverse("finance:reports")).content.decode()
    )


def test_report_without_centers_hides_the_tables(admin):
    report = admin.get(reverse("finance:reports"))
    assert not report.context["report"]["centros"]
    assert "por centro de custo" not in report.content.decode()


def test_reception_does_not_register(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_centros", clinica_a, Role.FRONT_DESK))
    assert reception.get(reverse(URL, args=["cost-centers"])).status_code == 403


def test_hidden_with_finance_off(clinica_a, admin):
    results = reverse(URL, args=["cost-centers"])
    assert results in admin.get(reverse("home")).content.decode()
    configure(
        clinica_a,
        GENERAL_MODULES - {ModuleCode.FINANCE, ModuleCode.ESTIMATES, ModuleCode.STAFF},
    )
    assert admin.get(results).status_code == 403
    assert results not in admin.get(reverse("home")).content.decode()
