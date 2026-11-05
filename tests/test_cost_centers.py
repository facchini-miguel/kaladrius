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
        "modo": "dividir",
        "parcelas": 1,
        "primeiro_vencimento": HOJE.isoformat(),
        "notes": "",
        **extra,
    }


def test_cadastro_e_nome_repetido(clinica_a, admin):
    url = reverse("finance:catalog_new", args=["cost-centers"])
    assert admin.post(url, {"name": " Consultório 1 ", "active": "on"}).status_code == 302
    with use_clinic(clinica_a):
        assert CostCenter.objects.get().name == "Consultório 1"
    repetido = admin.post(url, {"name": "consultório 1", "active": "on"})
    assert "name" in repetido.context["form"].errors
    results = admin.get(reverse(URL, args=["cost-centers"])).content.decode()
    assert "Consultório 1" in results and "Ativo" in results


def test_campo_so_aparece_com_centro_cadastrado(clinica_a, admin):
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


def test_lancamentos_guardam_o_centro(clinica_a, centro, admin):
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
            "parcelas": 1,
            "primeiro_vencimento": HOJE.isoformat(),
            "notes": "",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        assert Entry.objects.filter(cost_center=centro).count() == 2
        entry = Entry.objects.get(kind=Entry.Tipo.PAGAR)
    page = admin.get(reverse("finance:entry", args=[entry.pk])).content.decode()
    assert "Ortodontia" in page
    # Without a center the entry still saves (the field is optional).
    assert admin.post(reverse("finance:expense_new"), despesa(clinica_a)).status_code == 302


def test_relatorio_por_centro_de_custo(clinica_a, centro, admin):
    with use_clinic(clinica_a):
        aluguel = Category.objects.get(name="Aluguel")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        for amount, cost_center in ((Decimal("300"), centro), (Decimal("200"), None)):
            entry = services.criar_lancamento(
                clinic=clinica_a,
                kind=Entry.Tipo.PAGAR,
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
            services.receber(
                installment,
                user=None,
                amount=installment.amount,
                method="pix",
                account=cash_register,
            )
    relatorio = admin.get(reverse("finance:reports")).context["relatorio"]
    assert relatorio["centros"]
    assert {name: str(total) for name, total in relatorio["despesas_por_centro"]} == {
        "Ortodontia": "300.00",
        "Sem centro de custo": "200.00",
    }
    assert (
        "Despesas pagas por centro de custo"
        in admin.get(reverse("finance:reports")).content.decode()
    )


def test_relatorio_sem_centros_nao_mostra_os_quadros(admin):
    relatorio = admin.get(reverse("finance:reports"))
    assert not relatorio.context["relatorio"]["centros"]
    assert "por centro de custo" not in relatorio.content.decode()


def test_recepcao_nao_cadastra(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_centros", clinica_a, Role.FRONT_DESK))
    assert reception.get(reverse(URL, args=["cost-centers"])).status_code == 403


def test_some_com_o_financeiro_desligado(clinica_a, admin):
    results = reverse(URL, args=["cost-centers"])
    assert results in admin.get(reverse("home")).content.decode()
    configure(
        clinica_a,
        GENERAL_MODULES - {ModuleCode.FINANCE, ModuleCode.ESTIMATES, ModuleCode.STAFF},
    )
    assert admin.get(results).status_code == 403
    assert results not in admin.get(reverse("home")).content.decode()
