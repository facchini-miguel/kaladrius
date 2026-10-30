"""Closing the books (decision 096). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import servicos
from apps.financeiro.models import Categoria, Conta, Fechamento, Lancamento

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)
ANTEONTEM = HOJE - datetime.timedelta(days=2)
URL = reverse("financeiro:fechamento")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fechamento", clinica_a, Papel.ADMIN))


@pytest.fixture
def parcela(clinica_a):
    with usar_clinica(clinica_a):
        lancamento = servicos.criar_lancamento(
            clinica=clinica_a,
            tipo=Lancamento.Tipo.RECEBER,
            pessoa="Pagador fictício",
            descricao="Consulta",
            categoria=Categoria.objects.get(nome="Consulta"),
            valor_total=Decimal("300"),
            parcelas=1,
            primeiro_vencimento=ANTEONTEM,
            usuario=None,
        )
        return lancamento.parcelas.get()


def receber(clinica, parcela, data, valor="100"):
    with usar_clinica(clinica):
        return servicos.receber(
            parcela,
            usuario=None,
            valor=Decimal(valor),
            data=data,
            forma="pix",
            conta=Conta.objects.get(nome="Caixa"),
        )


def test_fechar_trava_pagamentos_e_estornos_no_periodo(clinica_a, parcela, admin):
    antigo = receber(clinica_a, parcela, ANTEONTEM)
    assert admin.post(URL, {"acao": "fechar", "ate": ONTEM.isoformat()}).status_code == 302
    with usar_clinica(clinica_a):
        assert servicos.fechado_ate(clinica_a.pk) == ONTEM
    with pytest.raises(ValidationError, match="fechado"):
        receber(clinica_a, parcela, ONTEM)
    with usar_clinica(clinica_a), pytest.raises(ValidationError, match="fechado"):
        servicos.estornar(antigo, motivo="erro", usuario=None)
    # Today is never closed: money keeps coming in.
    assert receber(clinica_a, parcela, HOJE).pk


def test_receber_pela_tela_mostra_o_erro(clinica_a, parcela, admin):
    with usar_clinica(clinica_a):
        servicos.fechar(clinica_a, ONTEM, usuario=None)
    resposta = admin.post(
        reverse("financeiro:receber_parcela", args=[parcela.pk]),
        {
            "data": ONTEM.isoformat(),
            "valor": "100",
            "forma": "pix",
            "conta": Conta.todos.get(clinica=clinica_a, nome="Caixa").pk,
        },
        follow=True,
    )
    assert "fechado até" in resposta.content.decode()


@pytest.mark.parametrize(
    ("ate", "mensagem"),
    [(HOJE, "ontem"), (HOJE + datetime.timedelta(days=3), "ontem")],
)
def test_nao_fecha_hoje_nem_o_futuro(clinica_a, ate, mensagem):
    with usar_clinica(clinica_a), pytest.raises(ValidationError, match=mensagem):
        servicos.fechar(clinica_a, ate, usuario=None)


def test_fechar_de_novo_so_para_frente_e_reabrir_com_motivo(clinica_a, admin):
    with usar_clinica(clinica_a):
        servicos.fechar(clinica_a, ANTEONTEM, usuario=None)
        with pytest.raises(ValidationError, match="já está fechado"):
            servicos.fechar(clinica_a, ANTEONTEM, usuario=None)
        servicos.fechar(clinica_a, ONTEM, usuario=None)
        with pytest.raises(ValidationError, match="motivo"):
            servicos.reabrir(clinica_a, ANTEONTEM, motivo=" ", usuario=None)
        with pytest.raises(ValidationError, match="anterior"):
            servicos.reabrir(clinica_a, ONTEM, motivo="erro", usuario=None)
    assert (
        admin.post(
            URL, {"acao": "reabrir", "ate": "", "motivo": "Lançamento esquecido"}
        ).status_code
        == 302
    )
    with usar_clinica(clinica_a):
        assert servicos.fechado_ate(clinica_a.pk) is None
        assert Fechamento.objects.count() == 3
    pagina = admin.get(URL).content.decode()
    assert "Lançamento esquecido" in pagina and "O financeiro está aberto" in pagina


def test_cada_clinica_tem_o_seu_fechamento(clinica_a, clinica_b):
    with usar_clinica(clinica_a):
        servicos.fechar(clinica_a, ONTEM, usuario=None)
    assert servicos.fechado_ate(clinica_b.pk) is None


def test_relatorio_mostra_o_fechamento(clinica_a, admin):
    with usar_clinica(clinica_a):
        servicos.fechar(clinica_a, ONTEM, usuario=None)
    assert "Financeiro fechado até" in admin.get(reverse("financeiro:relatorios")).content.decode()


def test_quem_pode_ver_fechar_e_reabrir(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_fechamento", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(URL).status_code == 403
    financeiro = cliente_de(criar_usuario("fin_fechamento", clinica_a, Papel.FINANCEIRO))
    assert financeiro.post(URL, {"acao": "fechar", "ate": ONTEM.isoformat()}).status_code == 302
    assert financeiro.post(URL, {"acao": "outra"}).status_code == 403


def test_demonstracao_so_consulta(clinica_a, criar_usuario, cliente_de):
    demo = cliente_de(criar_usuario("demo_fechamento", clinica_a, Papel.ADMIN, demonstracao=True))
    pagina = demo.get(URL)
    assert pagina.status_code == 200 and pagina.context["fechar_form"] is None
    assert demo.post(URL, {"acao": "fechar", "ate": ONTEM.isoformat()}).status_code == 403
    with usar_clinica(clinica_a):
        assert not Fechamento.objects.exists()
