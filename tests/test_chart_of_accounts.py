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

TODAY = timezone.localdate()


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_plano", clinic_a, Role.ADMIN))


def group(clinic, name, **extra):
    with use_clinic(clinic):
        return AccountGroup.objects.get(name=name, **extra)


def test_new_clinic_starts_with_the_basic_chart(clinic_a):
    with use_clinic(clinic_a):
        rent = Category.objects.get(name="Aluguel")
        assert str(rent.group) == "1 Ocupação"
        assert Category.objects.get(name="Comissões").group.name == "Pessoal"
        assert not Category.objects.filter(group=None).exists()
        assert AccountGroup.objects.filter(kind="income").count() == 2


def test_numbered_subgroup_and_moved_category(clinic_a, admin):
    staff_ = group(clinic_a, "Pessoal")
    response = admin.post(
        reverse("finance:group_new"),
        {
            "name": "Equipe da recepção",
            "kind": "expense",
            "parent": staff_.pk,
            "code": 1,
            "active": "on",
        },
    )
    assert response.status_code == 302
    sub = group(clinic_a, "Equipe da recepção")
    with use_clinic(clinic_a):
        assert sub.number == "2.1"
        salaries = Category.objects.get(name="Salários e encargos")
    edit = admin.post(
        reverse("finance:catalog_edit", args=["categories", salaries.pk]),
        {"name": salaries.name, "kind": "expense", "group": sub.pk, "active": "on"},
    )
    assert edit.status_code == 302
    page = admin.get(reverse("finance:chart_of_accounts")).content.decode()
    assert "2.1 Equipe da recepção" in page and "Salários e encargos" in page


def test_blank_code_gets_the_next_number(clinic_a, admin):
    """Review stage 3: a subgroup saved with a blank code had no number at all."""
    staff_ = group(clinic_a, "Pessoal")
    for name in ("Equipe A", "Equipe B"):
        data = {"name": name, "kind": "expense", "parent": staff_.pk, "code": "", "active": "on"}
        assert admin.post(reverse("finance:group_new"), data).status_code == 302
    with use_clinic(clinic_a):
        assert group(clinic_a, "Equipe A").number == "2.1"
        assert group(clinic_a, "Equipe B").number == "2.2"
    # A new top group goes after the five of the basic plan.
    top = {"name": "Investimentos", "kind": "expense", "parent": "", "code": "", "active": "on"}
    assert admin.post(reverse("finance:group_new"), top).status_code == 302
    with use_clinic(clinic_a):
        assert group(clinic_a, "Investimentos").number == "6"


def test_group_validations(clinic_a, admin):
    staff_ = group(clinic_a, "Pessoal")
    visit_list = group(clinic_a, "Atendimentos")
    url = reverse("finance:group_new")
    mixed = admin.post(url, {"name": "X", "kind": "expense", "parent": visit_list.pk})
    assert "parent" in mixed.context["form"].errors
    repeated_one = admin.post(url, {"name": "pessoal", "kind": "expense"})
    assert "name" in repeated_one.context["form"].errors
    # A group cannot go under itself or under one of its subgroups.
    with use_clinic(clinic_a):
        sub = AccountGroup.objects.create(name="Sub", kind="expense", parent=staff_)
    cycle = admin.post(
        reverse("finance:group_edit", args=[staff_.pk]),
        {"name": "Pessoal", "kind": "expense", "parent": sub.pk},
    )
    assert "parent" in cycle.context["form"].errors


def test_category_cannot_join_group_of_another_kind(clinic_a, admin):
    response = admin.post(
        reverse("finance:catalog_new", args=["categories"]),
        {
            "name": "Exames",
            "kind": "income",
            "group": group(clinic_a, "Pessoal").pk,
            "active": "on",
        },
    )
    assert "group" in response.context["form"].errors


def test_report_sums_the_subgroups(clinic_a, admin):
    with use_clinic(clinic_a):
        staff_ = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="expense", parent=staff_, code=1)
        salaries = Category.objects.get(name="Salários e encargos")
        salaries.group = sub
        salaries.save()
        standalone = Category.objects.create(name="Despesa avulsa", kind="expense")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        for category, amount in (
            (salaries, "1000"),
            (Category.objects.get(name="Comissões"), "300"),
            (standalone, "50"),
        ):
            entry = services.create_entry(
                clinic=clinic_a,
                kind=Entry.Kind.PAYABLE,
                payer="Fictício",
                description="Pagamento",
                category=category,
                total_amount=Decimal(amount),
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
    assert [(n, name, str(v)) for n, name, v in report["expenses_by_group"]] == [
        (0, "2 Pessoal", "1300.00"),
        (1, "2.1 Recepção", "1000.00"),
        (0, "Sem grupo", "50.00"),
    ]


def test_who_sees_the_chart(clinic_a, create_user, client_for):
    reception = client_for(create_user("recepcao_plano", clinic_a, Role.FRONT_DESK))
    assert reception.get(reverse("finance:chart_of_accounts")).status_code == 403


def test_migration_creates_basic_chart_in_existing_clinics():
    """Migration financeiro 0012 created the basic chart in the clinics that existed."""
    from apps.core.models import Clinic

    clinic = Clinic.objects.create(name="Clínica fictícia antiga")
    with use_clinic(clinic):
        # As the clinic was before 0012: categories and no chart of accounts.
        # The values of its time (decision 198).
        Category.objects.all().delete()
        AccountGroup.objects.all().delete()
        Category.objects.create(name="Aluguel", kind="despesa")
        Category.objects.create(name="Aluguel da sala", kind="despesa")
    apps = apps_at(("finance", "0012_plano_de_contas"))
    pairs_ = [
        (apps.get_model("core", "Clinica"), Clinic),
        (apps.get_model("finance", "GrupoContabil"), AccountGroup),
        (apps.get_model("finance", "Categoria"), Category),
    ]
    with tables_of_the_time(pairs_), connection.schema_editor() as editor:
        importlib.import_module("apps.finance.migrations.0012_plano_de_contas").plano_basico(
            apps, editor
        )
    with use_clinic(clinic):
        assert Category.objects.get(name="Aluguel").group.name == "Ocupação"
        assert Category.objects.get(name="Aluguel da sala").group is None
        assert AccountGroup.objects.count() == 7
