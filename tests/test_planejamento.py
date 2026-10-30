"""Yearly planning (decision 098): goals per group next to what was paid. Fictitious data."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import servicos
from apps.financeiro.models import Categoria, Conta, GrupoContabil, Lancamento, Planejamento

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
URL = reverse("financeiro:planejamento")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_planejamento", clinica_a, Papel.ADMIN))


def grupo(clinica, nome):
    with usar_clinica(clinica):
        return GrupoContabil.objects.get(nome=nome)


def pagar(clinica, categoria, valor, data=HOJE):
    with usar_clinica(clinica):
        lancamento = servicos.criar_lancamento(
            clinica=clinica,
            tipo=Lancamento.Tipo.PAGAR,
            pessoa="Fictício",
            descricao="Despesa",
            categoria=Categoria.objects.get(nome=categoria),
            valor_total=Decimal(valor),
            parcelas=1,
            primeiro_vencimento=data,
            usuario=None,
        )
        parcela = lancamento.parcelas.get()
        servicos.receber(
            parcela,
            usuario=None,
            valor=parcela.valor,
            data=data,
            forma="pix",
            conta=Conta.objects.get(nome="Caixa"),
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
    assert servicos.fracao_do_ano(2026, hoje) == esperado


def test_salvar_metas_no_formato_brasileiro(clinica_a, admin):
    ocupacao = grupo(clinica_a, "Ocupação")
    resposta = admin.post(f"{URL}?ano={HOJE.year}", {f"meta-{ocupacao.pk}": "12000,50"})
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert Planejamento.objects.get().valor == Decimal("12000.50")
    pagina = admin.get(f"{URL}?ano={HOJE.year}").content.decode()
    assert 'value="12000,50"' in pagina  # shown back with a comma, not as 12000.50
    # Blank removes the goal.
    admin.post(f"{URL}?ano={HOJE.year}", {f"meta-{ocupacao.pk}": ""})
    with usar_clinica(clinica_a):
        assert not Planejamento.objects.exists()


def test_realizado_e_percentual_somando_os_subgrupos(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = GrupoContabil.objects.get(nome="Ocupação")
        Planejamento.objects.create(ano=HOJE.year, grupo=ocupacao, valor=Decimal("1000"))
    pagar(clinica_a, "Aluguel", "250")
    pagar(clinica_a, "Manutenção", "50")
    pagar(clinica_a, "Aluguel", "999", data=datetime.date(HOJE.year - 1, 6, 1))  # other year
    despesas = admin.get(f"{URL}?ano={HOJE.year}").context["secoes"][1]
    linha = next(linha for linha in despesas["linhas"] if linha["grupo"] == ocupacao)
    assert (linha["realizado"], linha["percentual"]) == (Decimal("300.00"), 30)
    assert despesas["meta"] == Decimal("1000") and despesas["realizado"] == Decimal("300.00")


def test_meta_de_subgrupo_nao_conta_duas_vezes(clinica_a):
    with usar_clinica(clinica_a):
        pessoal = GrupoContabil.objects.get(nome="Pessoal")
        sub = GrupoContabil.objects.create(nome="Recepção", tipo="despesa", pai=pessoal)
        Planejamento.objects.create(ano=2026, grupo=pessoal, valor=Decimal("5000"))
        Planejamento.objects.create(ano=2026, grupo=sub, valor=Decimal("2000"))
        Planejamento.objects.create(
            ano=2026, grupo=GrupoContabil.objects.get(nome="Impostos"), valor=Decimal("700")
        )
        despesas = servicos.planejamento(2026, hoje=datetime.date(2026, 12, 31))["secoes"][1]
    assert despesas["meta"] == Decimal("5700")
    assert despesas["esperado"] == Decimal("5700.00")


def test_em_dia_para_receita_e_despesa(clinica_a):
    with usar_clinica(clinica_a):
        Planejamento.objects.create(
            ano=2026, grupo=GrupoContabil.objects.get(nome="Atendimentos"), valor=Decimal("1200")
        )
        Planejamento.objects.create(
            ano=2026, grupo=GrupoContabil.objects.get(nome="Impostos"), valor=Decimal("1200")
        )
        dados = servicos.planejamento(2026, hoje=datetime.date(2026, 12, 31))
    receita = next(linha for linha in dados["secoes"][0]["linhas"] if linha["meta"])
    despesa = next(linha for linha in dados["secoes"][1]["linhas"] if linha["meta"])
    # Nothing received yet: income is behind; nothing paid: expenses are within the goal.
    assert receita["em_dia"] is False and despesa["em_dia"] is True


def test_copiar_metas_do_ano_anterior(clinica_a, admin):
    with usar_clinica(clinica_a):
        ocupacao = GrupoContabil.objects.get(nome="Ocupação")
        impostos = GrupoContabil.objects.get(nome="Impostos")
        Planejamento.objects.create(ano=HOJE.year - 1, grupo=ocupacao, valor=Decimal("900"))
        Planejamento.objects.create(ano=HOJE.year - 1, grupo=impostos, valor=Decimal("300"))
        Planejamento.objects.create(ano=HOJE.year, grupo=impostos, valor=Decimal("400"))
    pagina = admin.get(f"{URL}?ano={HOJE.year}")
    assert pagina.context["tem_metas_anteriores"]
    admin.post(f"{URL}?ano={HOJE.year}", {"acao": "copiar"})
    with usar_clinica(clinica_a):
        deste_ano = dict(
            Planejamento.objects.filter(ano=HOJE.year).values_list("grupo__nome", "valor")
        )
    assert deste_ano == {"Ocupação": Decimal("900.00"), "Impostos": Decimal("400.00")}


def test_ano_invalido_volta_para_o_atual(admin):
    assert admin.get(URL, {"ano": "abc"}).context["ano"] == HOJE.year


def test_permissoes(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_planejamento", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(URL).status_code == 403
