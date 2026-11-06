"""Staff, salaries and the month's pay (decision 099). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import GENERAL_MODULES, ModuleCode, Role
from apps.core.modules import configure
from apps.finance import services as financeiro
from apps.finance.models import Entry
from apps.staff import services
from apps.staff.models import Employee, Payroll, Salary, suggested_overtime_rate

pytestmark = pytest.mark.django_db

OUTUBRO = datetime.date(2026, 10, 1)
FOLHA = reverse("staff:payroll")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_pessoal", clinica_a, Role.ADMIN))


@pytest.fixture
def ana(clinica_a):
    with use_clinic(clinica_a):
        employee = Employee.objects.create(
            name="Ana Fictícia", job_title="Recepcionista", hired_on=datetime.date(2025, 3, 1)
        )
        Salary.objects.create(
            employee=employee, amount=Decimal("2200"), effective_from=datetime.date(2025, 3, 1)
        )
        return employee


def test_registration_with_salary_and_raise_in_history(clinica_a, admin):
    response = admin.post(
        reverse("staff:new"),
        {
            "name": "Bruno Fictício",
            "tax_id": "529.982.247-25",
            "hired_on": "2026-01-05",
            "salary": "3000",
            "active": "on",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        bruno = Employee.objects.get()
        assert bruno.tax_id == "52998224725"
        assert bruno.salarios.get().effective_from == datetime.date(2026, 1, 5)  # admission date
    aumento = admin.post(
        reverse("staff:edit", args=[bruno.pk]),
        {
            "name": "Bruno Fictício",
            "tax_id": "52998224725",
            "hired_on": "2026-01-05",
            "salary": "3300",
            "salary_since": "2026-07-01",
            "active": "on",
        },
    )
    assert aumento.status_code == 302
    with use_clinic(clinica_a):
        assert bruno.salary_on(datetime.date(2026, 6, 30)) == Decimal("3000")
        assert bruno.salary_on(datetime.date(2026, 7, 1)) == Decimal("3300")
        assert bruno.salarios.count() == 2


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"tax_id": "111.111.111-11"}, "tax_id"),
        ({"salary": ""}, "salary"),
        ({"hired_on": "2026-05-01", "left_on": "2026-04-01"}, "left_on"),
    ],
)
def test_registration_validations(data, field, admin):
    base = {"name": "Fictício", "salary": "2000", "active": "on"}
    response = admin.post(reverse("staff:new"), {**base, **data})
    assert field in response.context["form"].errors


def test_payroll_prepares_the_month_employees(clinica_a, ana):
    with use_clinic(clinica_a):
        futuro = Employee.objects.create(
            name="Admitido depois", hired_on=datetime.date(2026, 11, 3)
        )
        Salary.objects.create(
            employee=futuro, amount=Decimal("2000"), effective_from=datetime.date(2026, 11, 3)
        )
        saiu = Employee.objects.create(name="Desligado antes", left_on=datetime.date(2026, 9, 30))
        Salary.objects.create(
            employee=saiu, amount=Decimal("2000"), effective_from=datetime.date(2025, 1, 1)
        )
        Employee.objects.create(name="Sem salário")
        folhas = services.prepare(OUTUBRO)
    assert [f.employee.name for f in folhas] == ["Ana Fictícia"]
    payroll = folhas[0]
    assert payroll.salary == Decimal("2200") and payroll.overtime_rate == suggested_overtime_rate(
        Decimal("2200")
    ) == Decimal("15.00")


def test_viewing_a_month_saves_no_payroll(clinica_a, ana, admin):
    for month in ("2026-10", "2030-01"):
        assert admin.get(FOLHA, {"month": month}).status_code == 200
    with use_clinic(clinica_a):
        assert not Payroll.objects.exists()


def test_total_calculation():
    payroll = Payroll(
        salary=Decimal("3000"),
        overtime_hours=Decimal("10"),
        overtime_rate=Decimal("20.45"),
        absences=2,
    )
    assert payroll.overtime_amount == Decimal("204.50")
    assert payroll.absence_deduction == Decimal("200.00")
    assert payroll.total == Decimal("3004.50")


def test_save_and_post_to_finance(clinica_a, ana, admin):
    page = admin.get(FOLHA, {"month": "2026-10"})
    payroll, form = page.context["rows"][0]
    prefixo = form.prefix
    data = {
        f"{prefixo}-overtime_hours": "10",
        f"{prefixo}-overtime_rate": "15,00",
        f"{prefixo}-absences": "1",
        f"{prefixo}-observacao": "",
    }
    assert payroll.pk is None  # looking at the month stored nothing
    assert admin.post(f"{FOLHA}?month=2026-10", data).status_code == 302
    with use_clinic(clinica_a):
        payroll = Payroll.objects.get(employee=ana, period=OUTUBRO)
        assert payroll.total == Decimal("2276.67")  # 2200 + 150 − 73,33
        category = page.context["post_form"].fields["category"].initial
    assert category.name == "Salários e encargos"
    response = admin.post(
        f"{FOLHA}?month=2026-10",
        {**data, "action": "lancar", "category": category.pk, "due_date": "2026-11-05"},
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        payroll.refresh_from_db()
        entry = payroll.entry
        assert (entry.kind, entry.payer, entry.total_amount) == (
            Entry.Kind.PAYABLE,
            "Ana Fictícia",
            Decimal("2276.67"),
        )
        assert entry.parcelas.get().due_date == datetime.date(2026, 11, 5)
    # A launched line is read-only and is not launched twice.
    row = admin.get(FOLHA, {"month": "2026-10"}).context["rows"][0]
    assert row[1] is None
    with use_clinic(clinica_a):
        assert (
            services.post_payroll(
                [payroll], category=category, due_date=datetime.date(2026, 11, 5), user=None
            )
            == 0
        )
        # Cancelling the payable in finance opens the line again.
        financeiro.cancel(entry, reason="Refazer", user=None)
        payroll.refresh_from_db()
        assert not payroll.is_posted


def test_zero_total_is_not_posted(clinica_a, ana):
    with use_clinic(clinica_a):
        payroll = services.prepare(OUTUBRO)[0]
        payroll.absences = 30
        payroll.save()
        with pytest.raises(ValidationError, match="maior que zero"):
            services.post_payroll([payroll], category=None, due_date=OUTUBRO, user=None)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_only_admin_and_finance_see_salaries(role, clinica_a, ana, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("sem_pessoal", clinica_a, role))
    for url in (FOLHA, reverse("staff:list"), reverse("staff:employee", args=[ana.pk])):
        assert cliente.get(url).status_code == 403, url


def test_finance_role_posts_payroll(clinica_a, ana, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("fin_pessoal", clinica_a, Role.FINANCE))
    assert cliente.get(FOLHA).status_code == 200


def test_staff_module_on_off_and_depends_on_finance(clinica_a, admin):
    assert reverse("staff:payroll") in admin.get(reverse("home")).content.decode()
    configure(clinica_a, GENERAL_MODULES - {ModuleCode.STAFF})
    assert admin.get(FOLHA).status_code == 403
    with pytest.raises(ValidationError):
        configure(clinica_a, GENERAL_MODULES - {ModuleCode.FINANCE, ModuleCode.ESTIMATES})
