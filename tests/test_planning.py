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


def grupo(clinic, name):
    with usar_clinica(clinic):
        return AccountGroup.objects.get(name=name)


def pagar(clinic, categoria, amount, data=HOJE):
    with usar_clinica(clinic):
        entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.PAGAR,
            pessoa="Fictício",
            description="Despesa",
            categoria=Category.objects.get(name=categoria),
            valor_total=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=data,
            user=None,
        )
        parcela = entry.parcelas.get()
        services.receber(
            parcela,
            user=None,
            amount=parcela.amount,
            data=data,
            forma="pix",
            conta=FinancialAccount.objects.get(name="Caixa"),
        )


@pytest.mark.parametrize(
    ("hoje", "esperado"),
    [
        (datetime.date(2025, 12, 31), Decimal(0)),
        (datetime.date(2027, 1, 1), Decimal(1)),
        (datetime.date(2026, 1, 1), Decimal(1) / Decimal(365)),
    ],
)
def test_fracao_do_ano(hoje, esperado):
    assert services.fracao_do_ano(2026, hoje) == esperado


def test_salvar_metas_no_formato_brasileiro(clinica_a, admin):
    ocupacao = grupo(clinica_a, "Ocupação")
    # With the thousands dot, as people type it (review stage 3: it was refused).
    resposta = admin.post(f"{URL}?ano={HOJE.year}", {f"meta-{ocupacao.pk}": "12.000,50"})
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert Planning.objects.get().amount == Decimal("12000.50")
    pagina = admin.get(f"{URL}?ano={HOJE.year}").content.decode()
    assert 'value="12000,50"' in pagina  # shown back with a comma, not as 12000.50
    # Blank removes the goal.
    admin.post(f"{URL}?ano={HOJE.year}", {f"meta-{ocupacao.pk}": ""})
    with usar_clinica(clinica_a):
        assert not Planning.objects.exists()


def test_realizado_e_percentual_somando_os_subgrupos(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        Planning.objects.create(ano=HOJE.year, grupo=ocupacao, amount=Decimal("1000"))
    pagar(clinica_a, "Aluguel", "250")
    pagar(clinica_a, "Manutenção", "50")
    pagar(clinica_a, "Aluguel", "999", data=datetime.date(HOJE.year - 1, 6, 1))  # other year
    despesas = admin.get(f"{URL}?ano={HOJE.year}").context["secoes"][1]
    linha = next(linha for linha in despesas["linhas"] if linha["grupo"] == ocupacao)
    assert (linha["realizado"], linha["percentual"]) == (Decimal("300.00"), 30)
    assert despesas["meta"] == Decimal("1000") and despesas["realizado"] == Decimal("300.00")


def test_meta_de_subgrupo_nao_conta_duas_vezes(clinica_a):
    with usar_clinica(clinica_a):
        pessoal = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", pai=pessoal)
        Planning.objects.create(ano=2026, grupo=pessoal, amount=Decimal("5000"))
        Planning.objects.create(ano=2026, grupo=sub, amount=Decimal("2000"))
        Planning.objects.create(
            ano=2026, grupo=AccountGroup.objects.get(name="Impostos"), amount=Decimal("700")
        )
        despesas = services.planejamento(2026, hoje=datetime.date(2026, 12, 31))["secoes"][1]
    assert despesas["meta"] == Decimal("5700")
    assert despesas["esperado"] == Decimal("5700.00")


def test_em_dia_para_receita_e_despesa(clinica_a):
    with usar_clinica(clinica_a):
        Planning.objects.create(
            ano=2026, grupo=AccountGroup.objects.get(name="Atendimentos"), amount=Decimal("1200")
        )
        Planning.objects.create(
            ano=2026, grupo=AccountGroup.objects.get(name="Impostos"), amount=Decimal("1200")
        )
        dados = services.planejamento(2026, hoje=datetime.date(2026, 12, 31))
    receita = next(linha for linha in dados["secoes"][0]["linhas"] if linha["meta"])
    despesa = next(linha for linha in dados["secoes"][1]["linhas"] if linha["meta"])
    # Nothing received yet: income is behind; nothing paid: expenses are within the goal.
    assert receita["em_dia"] is False and despesa["em_dia"] is True


def test_copiar_metas_do_ano_anterior(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = AccountGroup.objects.get(name="Ocupação")
        impostos = AccountGroup.objects.get(name="Impostos")
        Planning.objects.create(ano=HOJE.year - 1, grupo=ocupacao, amount=Decimal("900"))
        Planning.objects.create(ano=HOJE.year - 1, grupo=impostos, amount=Decimal("300"))
        Planning.objects.create(ano=HOJE.year, grupo=impostos, amount=Decimal("400"))
    pagina = admin.get(f"{URL}?ano={HOJE.year}")
    assert pagina.context["tem_metas_anteriores"]
    admin.post(f"{URL}?ano={HOJE.year}", {"acao": "copiar"})
    with usar_clinica(clinica_a):
        deste_ano = dict(
            Planning.objects.filter(ano=HOJE.year).values_list("grupo__name", "amount")
        )
    assert deste_ano == {"Ocupação": Decimal("900.00"), "Impostos": Decimal("400.00")}


def test_ano_invalido_volta_para_o_atual(admin):
    assert admin.get(URL, {"ano": "abc"}).context["ano"] == HOJE.year


def test_permissoes(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_planejamento", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(URL).status_code == 403
