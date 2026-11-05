"""Staff, salaries and the month's pay (decision 099). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modules import configurar
from apps.finance import services as financeiro
from apps.finance.models import Entry
from apps.staff import services
from apps.staff.models import Employee, Payroll, Salary, hora_extra_sugerida

pytestmark = pytest.mark.django_db

OUTUBRO = datetime.date(2026, 10, 1)
FOLHA = reverse("staff:payroll")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_pessoal", clinica_a, Papel.ADMIN))


@pytest.fixture
def ana(clinica_a):
    with usar_clinica(clinica_a):
        employee = Employee.objects.create(
            name="Ana Fictícia", job_title="Recepcionista", hired_on=datetime.date(2025, 3, 1)
        )
        Salary.objects.create(
            employee=employee, amount=Decimal("2200"), effective_from=datetime.date(2025, 3, 1)
        )
        return employee


def test_cadastro_com_salario_e_aumento_no_historico(clinica_a, admin):
    resposta = admin.post(
        reverse("staff:new"),
        {
            "name": "Bruno Fictício",
            "tax_id": "529.982.247-25",
            "hired_on": "2026-01-05",
            "salary": "3000",
            "active": "on",
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
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
            "salario_desde": "2026-07-01",
            "active": "on",
        },
    )
    assert aumento.status_code == 302
    with usar_clinica(clinica_a):
        assert bruno.salario_em(datetime.date(2026, 6, 30)) == Decimal("3000")
        assert bruno.salario_em(datetime.date(2026, 7, 1)) == Decimal("3300")
        assert bruno.salarios.count() == 2


@pytest.mark.parametrize(
    ("dados", "campo"),
    [
        ({"tax_id": "111.111.111-11"}, "tax_id"),
        ({"salary": ""}, "salary"),
        ({"hired_on": "2026-05-01", "left_on": "2026-04-01"}, "left_on"),
    ],
)
def test_validacoes_do_cadastro(dados, campo, admin):
    base = {"name": "Fictício", "salary": "2000", "active": "on"}
    resposta = admin.post(reverse("staff:new"), {**base, **dados})
    assert campo in resposta.context["form"].errors


def test_folha_prepara_os_funcionarios_do_mes(clinica_a, ana):
    with usar_clinica(clinica_a):
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
        folhas = services.preparar(OUTUBRO)
    assert [f.employee.name for f in folhas] == ["Ana Fictícia"]
    folha = folhas[0]
    assert folha.salary == Decimal("2200") and folha.overtime_rate == hora_extra_sugerida(
        Decimal("2200")
    ) == Decimal("15.00")


def test_olhar_um_mes_nao_grava_folhas(clinica_a, ana, admin):
    for mes in ("2026-10", "2030-01"):
        assert admin.get(FOLHA, {"mes": mes}).status_code == 200
    with usar_clinica(clinica_a):
        assert not Payroll.objects.exists()


def test_calculo_do_total():
    folha = Payroll(
        salary=Decimal("3000"),
        overtime_hours=Decimal("10"),
        overtime_rate=Decimal("20.45"),
        absences=2,
    )
    assert folha.valor_horas_extras == Decimal("204.50")
    assert folha.desconto_faltas == Decimal("200.00")
    assert folha.total == Decimal("3004.50")


def test_salvar_e_lancar_no_financeiro(clinica_a, ana, admin):
    pagina = admin.get(FOLHA, {"mes": "2026-10"})
    folha, form = pagina.context["linhas"][0]
    prefixo = form.prefix
    dados = {
        f"{prefixo}-overtime_hours": "10",
        f"{prefixo}-overtime_rate": "15,00",
        f"{prefixo}-absences": "1",
        f"{prefixo}-observacao": "",
    }
    assert folha.pk is None  # looking at the month stored nothing
    assert admin.post(f"{FOLHA}?mes=2026-10", dados).status_code == 302
    with usar_clinica(clinica_a):
        folha = Payroll.objects.get(employee=ana, period=OUTUBRO)
        assert folha.total == Decimal("2276.67")  # 2200 + 150 − 73,33
        category = pagina.context["lancar_form"].fields["category"].initial
    assert category.name == "Salários e encargos"
    resposta = admin.post(
        f"{FOLHA}?mes=2026-10",
        {**dados, "acao": "lancar", "category": category.pk, "due_date": "2026-11-05"},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        folha.refresh_from_db()
        entry = folha.entry
        assert (entry.kind, entry.payer, entry.total_amount) == (
            Entry.Tipo.PAGAR,
            "Ana Fictícia",
            Decimal("2276.67"),
        )
        assert entry.parcelas.get().due_date == datetime.date(2026, 11, 5)
    # A launched line is read-only and is not launched twice.
    linha = admin.get(FOLHA, {"mes": "2026-10"}).context["linhas"][0]
    assert linha[1] is None
    with usar_clinica(clinica_a):
        assert (
            services.lancar(
                [folha], category=category, due_date=datetime.date(2026, 11, 5), user=None
            )
            == 0
        )
        # Cancelling the payable in finance opens the line again.
        financeiro.cancelar(entry, reason="Refazer", user=None)
        folha.refresh_from_db()
        assert not folha.lancada


def test_total_zero_nao_e_lancado(clinica_a, ana):
    with usar_clinica(clinica_a):
        folha = services.preparar(OUTUBRO)[0]
        folha.absences = 30
        folha.save()
        with pytest.raises(ValidationError, match="maior que zero"):
            services.lancar([folha], category=None, due_date=OUTUBRO, user=None)


@pytest.mark.parametrize("role", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_administrador_e_financeiro_veem_salarios(
    role, clinica_a, ana, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("sem_pessoal", clinica_a, role))
    for url in (FOLHA, reverse("staff:list"), reverse("staff:employee", args=[ana.pk])):
        assert cliente.get(url).status_code == 403, url


def test_perfil_financeiro_lanca_a_folha(clinica_a, ana, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("fin_pessoal", clinica_a, Papel.FINANCEIRO))
    assert cliente.get(FOLHA).status_code == 200


def test_modulo_pessoal_liga_desliga_e_depende_do_financeiro(clinica_a, admin):
    assert reverse("staff:payroll") in admin.get(reverse("home")).content.decode()
    configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.PESSOAL})
    assert admin.get(FOLHA).status_code == 403
    with pytest.raises(ValidationError):
        configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.FINANCEIRO, ModuloClinico.ORCAMENTOS})
