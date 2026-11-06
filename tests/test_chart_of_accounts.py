"""Chart of accounts (decision 097): groups in a tree, totals rolled up. Fictitious data."""

import importlib
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance import services
from apps.finance.models import AccountGroup, Category, Entry, FinancialAccount
from tests.era import apps_at, tables_of_the_time

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_plano", clinica_a, Role.ADMIN))


def group(clinic, name, **extra):
    with use_clinic(clinic):
        return AccountGroup.objects.get(name=name, **extra)


def test_new_clinic_starts_with_the_basic_chart(clinica_a):
    with use_clinic(clinica_a):
        aluguel = Category.objects.get(name="Aluguel")
        assert str(aluguel.group) == "1 Ocupação"
        assert Category.objects.get(name="Comissões").group.name == "Pessoal"
        assert not Category.objects.filter(group=None).exists()
        assert AccountGroup.objects.filter(kind="receita").count() == 2


def test_numbered_subgroup_and_moved_category(clinica_a, admin):
    pessoal = group(clinica_a, "Pessoal")
    response = admin.post(
        reverse("finance:group_new"),
        {
            "name": "Equipe da recepção",
            "kind": "despesa",
            "parent": pessoal.pk,
            "code": 1,
            "active": "on",
        },
    )
    assert response.status_code == 302
    sub = group(clinica_a, "Equipe da recepção")
    with use_clinic(clinica_a):
        assert sub.number == "2.1"
        salarios = Category.objects.get(name="Salários e encargos")
    editar = admin.post(
        reverse("finance:catalog_edit", args=["categories", salarios.pk]),
        {"name": salarios.name, "kind": "despesa", "group": sub.pk, "active": "on"},
    )
    assert editar.status_code == 302
    page = admin.get(reverse("finance:chart_of_accounts")).content.decode()
    assert "2.1 Equipe da recepção" in page and "Salários e encargos" in page


def test_blank_code_gets_the_next_number(clinica_a, admin):
    """Review stage 3: a subgroup saved with a blank code had no number at all."""
    pessoal = group(clinica_a, "Pessoal")
    for name in ("Equipe A", "Equipe B"):
        data = {"name": name, "kind": "despesa", "parent": pessoal.pk, "code": "", "active": "on"}
        assert admin.post(reverse("finance:group_new"), data).status_code == 302
    with use_clinic(clinica_a):
        assert group(clinica_a, "Equipe A").number == "2.1"
        assert group(clinica_a, "Equipe B").number == "2.2"
    # A new top group goes after the five of the basic plan.
    topo = {"name": "Investimentos", "kind": "despesa", "parent": "", "code": "", "active": "on"}
    assert admin.post(reverse("finance:group_new"), topo).status_code == 302
    with use_clinic(clinica_a):
        assert group(clinica_a, "Investimentos").number == "6"


def test_group_validations(clinica_a, admin):
    pessoal = group(clinica_a, "Pessoal")
    atendimentos = group(clinica_a, "Atendimentos")
    url = reverse("finance:group_new")
    misturado = admin.post(url, {"name": "X", "kind": "despesa", "parent": atendimentos.pk})
    assert "parent" in misturado.context["form"].errors
    repetido = admin.post(url, {"name": "pessoal", "kind": "despesa"})
    assert "name" in repetido.context["form"].errors
    # A group cannot go under itself or under one of its subgroups.
    with use_clinic(clinica_a):
        sub = AccountGroup.objects.create(name="Sub", kind="despesa", parent=pessoal)
    ciclo = admin.post(
        reverse("finance:group_edit", args=[pessoal.pk]),
        {"name": "Pessoal", "kind": "despesa", "parent": sub.pk},
    )
    assert "parent" in ciclo.context["form"].errors


def test_category_cannot_join_group_of_another_kind(clinica_a, admin):
    response = admin.post(
        reverse("finance:catalog_new", args=["categories"]),
        {
            "name": "Exames",
            "kind": "receita",
            "group": group(clinica_a, "Pessoal").pk,
            "active": "on",
        },
    )
    assert "group" in response.context["form"].errors


def test_report_sums_the_subgroups(clinica_a, admin):
    with use_clinic(clinica_a):
        pessoal = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", parent=pessoal, code=1)
        salarios = Category.objects.get(name="Salários e encargos")
        salarios.group = sub
        salarios.save()
        avulsa = Category.objects.create(name="Despesa avulsa", kind="despesa")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        for category, amount in (
            (salarios, "1000"),
            (Category.objects.get(name="Comissões"), "300"),
            (avulsa, "50"),
        ):
            entry = services.create_entry(
                clinic=clinica_a,
                kind=Entry.Kind.PAYABLE,
                payer="Fictício",
                description="Pagamento",
                category=category,
                total_amount=Decimal(amount),
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
    assert [(n, name, str(v)) for n, name, v in report["despesas_por_grupo"]] == [
        (0, "2 Pessoal", "1300.00"),
        (1, "2.1 Recepção", "1000.00"),
        (0, "Sem grupo", "50.00"),
    ]


def test_who_sees_the_chart(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_plano", clinica_a, Role.FRONT_DESK))
    assert reception.get(reverse("finance:chart_of_accounts")).status_code == 403


def test_migration_creates_basic_chart_in_existing_clinics():
    """Migration financeiro 0012 created the basic chart in the clinics that existed."""
    from apps.core.models import Clinic

    clinic = Clinic.objects.create(name="Clínica fictícia antiga")
    with use_clinic(clinic):
        # As the clinic was before 0012: categories and no chart of accounts.
        Category.objects.all().delete()
        AccountGroup.objects.all().delete()
        Category.objects.create(name="Aluguel", kind="despesa")
        Category.objects.create(name="Aluguel da sala", kind="despesa")
    apps = apps_at(("financeiro", "0012_plano_de_contas"))
    pares = [
        (apps.get_model("core", "Clinica"), Clinic),
        (apps.get_model("financeiro", "GrupoContabil"), AccountGroup),
        (apps.get_model("financeiro", "Categoria"), Category),
    ]
    with tables_of_the_time(pares), connection.schema_editor() as editor:
        importlib.import_module("apps.finance.migrations.0012_plano_de_contas").plano_basico(
            apps, editor
        )
    with use_clinic(clinic):
        assert Category.objects.get(name="Aluguel").group.name == "Ocupação"
        assert Category.objects.get(name="Aluguel da sala").group is None
        assert AccountGroup.objects.count() == 7
