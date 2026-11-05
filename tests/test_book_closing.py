"""Closing the books (decision 096). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.finance import services
from apps.finance.models import BookClosing, Category, Entry, FinancialAccount

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)
ANTEONTEM = HOJE - datetime.timedelta(days=2)
URL = reverse("finance:closing")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fechamento", clinica_a, Papel.ADMIN))


@pytest.fixture
def installment(clinica_a):
    with usar_clinica(clinica_a):
        entry = services.criar_lancamento(
            clinic=clinica_a,
            kind=Entry.Tipo.RECEBER,
            payer="Pagador fictício",
            description="Consulta",
            category=Category.objects.get(name="Consulta"),
            total_amount=Decimal("300"),
            parcelas=1,
            primeiro_vencimento=ANTEONTEM,
            user=None,
        )
        return entry.parcelas.get()


def receber(clinic, installment, date, amount="100"):
    with usar_clinica(clinic):
        return services.receber(
            installment,
            user=None,
            amount=Decimal(amount),
            date=date,
            method="pix",
            account=FinancialAccount.objects.get(name="Caixa"),
        )


def test_fechar_trava_pagamentos_e_estornos_no_periodo(clinica_a, installment, admin):
    old = receber(clinica_a, installment, ANTEONTEM)
    assert admin.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 302
    with usar_clinica(clinica_a):
        assert services.fechado_ate(clinica_a.pk) == ONTEM
    with pytest.raises(ValidationError, match="fechado"):
        receber(clinica_a, installment, ONTEM)
    with usar_clinica(clinica_a), pytest.raises(ValidationError, match="fechado"):
        services.estornar(old, reason="erro", user=None)
    # Today is never closed: money keeps coming in.
    assert receber(clinica_a, installment, HOJE).pk


def test_receber_pela_tela_mostra_o_erro(clinica_a, installment, admin):
    with usar_clinica(clinica_a):
        services.fechar(clinica_a, ONTEM, user=None)
    response = admin.post(
        reverse("finance:receive_installment", args=[installment.pk]),
        {
            "date": ONTEM.isoformat(),
            "amount": "100",
            "method": "pix",
            "account": FinancialAccount.todos.get(clinic=clinica_a, name="Caixa").pk,
        },
        follow=True,
    )
    assert "fechado até" in response.content.decode()


@pytest.mark.parametrize(
    ("until", "message"),
    [(HOJE, "ontem"), (HOJE + datetime.timedelta(days=3), "ontem")],
)
def test_nao_fecha_hoje_nem_o_futuro(clinica_a, until, message):
    with usar_clinica(clinica_a), pytest.raises(ValidationError, match=message):
        services.fechar(clinica_a, until, user=None)


def test_fechar_de_novo_so_para_frente_e_reabrir_com_motivo(clinica_a, admin):
    with usar_clinica(clinica_a):
        services.fechar(clinica_a, ANTEONTEM, user=None)
        with pytest.raises(ValidationError, match="já está fechado"):
            services.fechar(clinica_a, ANTEONTEM, user=None)
        services.fechar(clinica_a, ONTEM, user=None)
        with pytest.raises(ValidationError, match="motivo"):
            services.reabrir(clinica_a, ANTEONTEM, reason=" ", user=None)
        with pytest.raises(ValidationError, match="anterior"):
            services.reabrir(clinica_a, ONTEM, reason="erro", user=None)
    assert (
        admin.post(
            URL, {"acao": "reabrir", "until": "", "reason": "Lançamento esquecido"}
        ).status_code
        == 302
    )
    with usar_clinica(clinica_a):
        assert services.fechado_ate(clinica_a.pk) is None
        assert BookClosing.objects.count() == 3
    page = admin.get(URL).content.decode()
    assert "Lançamento esquecido" in page and "O financeiro está aberto" in page


def test_cada_clinica_tem_o_seu_fechamento(clinica_a, clinica_b):
    with usar_clinica(clinica_a):
        services.fechar(clinica_a, ONTEM, user=None)
    assert services.fechado_ate(clinica_b.pk) is None


def test_relatorio_mostra_o_fechamento(clinica_a, admin):
    with usar_clinica(clinica_a):
        services.fechar(clinica_a, ONTEM, user=None)
    assert "Financeiro fechado até" in admin.get(reverse("finance:reports")).content.decode()


def test_quem_pode_ver_fechar_e_reabrir(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_fechamento", clinica_a, Papel.RECEPCAO))
    assert reception.get(URL).status_code == 403
    financeiro = cliente_de(criar_usuario("fin_fechamento", clinica_a, Papel.FINANCEIRO))
    assert financeiro.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 302
    assert financeiro.post(URL, {"acao": "outra"}).status_code == 403


def test_demonstracao_so_consulta(clinica_a, criar_usuario, cliente_de):
    demo = cliente_de(criar_usuario("demo_fechamento", clinica_a, Papel.ADMIN, demo=True))
    page = demo.get(URL)
    assert page.status_code == 200 and page.context["fechar_form"] is None
    assert demo.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 403
    with usar_clinica(clinica_a):
        assert not BookClosing.objects.exists()
