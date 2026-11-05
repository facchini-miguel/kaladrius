"""Yearly planning (decision 098): goals per group next to what was paid. Fictitious data."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.finance import services
from apps.finance.models import AccountGroup, Category, Entry, FinancialAccount, Planning

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
URL = reverse("finance:planning")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_planejamento", clinica_a, Papel.ADMIN))


def group(clinic, name):
    with usar_clinica(clinic):
        return AccountGroup.objects.get(name=name)


def pagar(clinic, category, amount, date=HOJE):
    with usar_clinica(clinic):
        entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.PAGAR,
            payer="Fictício",
            description="Despesa",
            category=Category.objects.get(name=category),
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=None,
        )
        installment = entry.parcelas.get()
        services.receber(
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
def test_fracao_do_ano(today, esperado):
    assert services.fracao_do_ano(2026, today) == esperado


def test_salvar_metas_no_formato_brasileiro(clinica_a, admin):
    ocupacao = group(clinica_a, "Ocupação")
    # With the thousands dot, as people type it (review stage 3: it was refused).
    response = admin.post(f"{URL}?year={HOJE.year}", {f"meta-{ocupacao.pk}": "12.000,50"})
    assert response.status_code == 302
    with usar_clinica(clinica_a):
        assert Planning.objects.get().amount == Decimal("12000.50")
    page = admin.get(f"{URL}?year={HOJE.year}").content.decode()
    assert 'value="12000,50"' in page  # shown back with a comma, not as 12000.50
    # Blank removes the goal.
    admin.post(f"{URL}?year={HOJE.year}", {f"meta-{ocupacao.pk}": ""})
    with usar_clinica(clinica_a):
        assert not Planning.objects.exists()


def test_realizado_e_percentual_somando_os_subgrupos(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        Planning.objects.create(year=HOJE.year, group=ocupacao, amount=Decimal("1000"))
    pagar(clinica_a, "Aluguel", "250")
    pagar(clinica_a, "Manutenção", "50")
    pagar(clinica_a, "Aluguel", "999", date=datetime.date(HOJE.year - 1, 6, 1))  # other year
    despesas = admin.get(f"{URL}?year={HOJE.year}").context["secoes"][1]
    row = next(row for row in despesas["linhas"] if row["group"] == ocupacao)
    assert (row["realizado"], row["percentage"]) == (Decimal("300.00"), 30)
    assert despesas["meta"] == Decimal("1000") and despesas["realizado"] == Decimal("300.00")


def test_meta_de_subgrupo_nao_conta_duas_vezes(clinica_a):
    with usar_clinica(clinica_a):
        pessoal = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", parent=pessoal)
        Planning.objects.create(year=2026, group=pessoal, amount=Decimal("5000"))
        Planning.objects.create(year=2026, group=sub, amount=Decimal("2000"))
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("700")
        )
        despesas = services.planejamento(2026, today=datetime.date(2026, 12, 31))["secoes"][1]
    assert despesas["meta"] == Decimal("5700")
    assert despesas["esperado"] == Decimal("5700.00")


def test_em_dia_para_receita_e_despesa(clinica_a):
    with usar_clinica(clinica_a):
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Atendimentos"), amount=Decimal("1200")
        )
        Planning.objects.create(
            year=2026, group=AccountGroup.objects.get(name="Impostos"), amount=Decimal("1200")
        )
        data = services.planejamento(2026, today=datetime.date(2026, 12, 31))
    receita = next(row for row in data["secoes"][0]["linhas"] if row["meta"])
    despesa = next(row for row in data["secoes"][1]["linhas"] if row["meta"])
    # Nothing received yet: income is behind; nothing paid: expenses are within the goal.
    assert receita["em_dia"] is False and despesa["em_dia"] is True


def test_copiar_metas_do_ano_anterior(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        impostos = AccountGroup.objects.get(name="Impostos")
        Planning.objects.create(year=HOJE.year - 1, group=ocupacao, amount=Decimal("900"))
        Planning.objects.create(year=HOJE.year - 1, group=impostos, amount=Decimal("300"))
        Planning.objects.create(year=HOJE.year, group=impostos, amount=Decimal("400"))
    page = admin.get(f"{URL}?year={HOJE.year}")
    assert page.context["tem_metas_anteriores"]
    admin.post(f"{URL}?year={HOJE.year}", {"acao": "copiar"})
    with usar_clinica(clinica_a):
        deste_ano = dict(
            Planning.objects.filter(year=HOJE.year).values_list("group__name", "amount")
        )
    assert deste_ano == {"Ocupação": Decimal("900.00"), "Impostos": Decimal("400.00")}


def test_ano_invalido_volta_para_o_atual(admin):
    assert admin.get(URL, {"year": "abc"}).context["year"] == HOJE.year


def test_permissoes(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_planejamento", clinica_a, Papel.RECEPCAO))
    assert reception.get(URL).status_code == 403
