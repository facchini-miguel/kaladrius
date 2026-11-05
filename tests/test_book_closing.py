"""Closing the books (decision 096). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance import services
from apps.finance.models import BookClosing, Category, Entry, FinancialAccount

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)
ANTEONTEM = HOJE - datetime.timedelta(days=2)
URL = reverse("finance:closing")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fechamento", clinica_a, Role.ADMIN))


@pytest.fixture
def installment(clinica_a):
    with use_clinic(clinica_a):
        entry = services.create_entry(
            clinic=clinica_a,
            kind=Entry.Kind.RECEIVABLE,
            payer="Pagador fictício",
            description="Consulta",
            category=Category.objects.get(name="Consulta"),
            total_amount=Decimal("300"),
            parcelas=1,
            primeiro_vencimento=ANTEONTEM,
            user=None,
        )
        return entry.parcelas.get()


def receive(clinic, installment, date, amount="100"):
    with use_clinic(clinic):
        return services.receive(
            installment,
            user=None,
            amount=Decimal(amount),
            date=date,
            method="pix",
            account=FinancialAccount.objects.get(name="Caixa"),
        )


def test_closing_locks_payments_and_reversals_in_the_period(clinica_a, installment, admin):
    old = receive(clinica_a, installment, ANTEONTEM)
    assert admin.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 302
    with use_clinic(clinica_a):
        assert services.closed_until(clinica_a.pk) == ONTEM
    with pytest.raises(ValidationError, match="fechado"):
        receive(clinica_a, installment, ONTEM)
    with use_clinic(clinica_a), pytest.raises(ValidationError, match="fechado"):
        services.reverse_payment(old, reason="erro", user=None)
    # Today is never closed: money keeps coming in.
    assert receive(clinica_a, installment, HOJE).pk


def test_receiving_on_screen_shows_the_error(clinica_a, installment, admin):
    with use_clinic(clinica_a):
        services.close_books(clinica_a, ONTEM, user=None)
    response = admin.post(
        reverse("finance:receive_installment", args=[installment.pk]),
        {
            "date": ONTEM.isoformat(),
            "amount": "100",
            "method": "pix",
            "account": FinancialAccount.all_objects.get(clinic=clinica_a, name="Caixa").pk,
        },
        follow=True,
    )
    assert "fechado até" in response.content.decode()


@pytest.mark.parametrize(
    ("until", "message"),
    [(HOJE, "ontem"), (HOJE + datetime.timedelta(days=3), "ontem")],
)
def test_does_not_close_today_or_the_future(clinica_a, until, message):
    with use_clinic(clinica_a), pytest.raises(ValidationError, match=message):
        services.close_books(clinica_a, until, user=None)


def test_close_again_only_forward_and_reopen_with_reason(clinica_a, admin):
    with use_clinic(clinica_a):
        services.close_books(clinica_a, ANTEONTEM, user=None)
        with pytest.raises(ValidationError, match="já está fechado"):
            services.close_books(clinica_a, ANTEONTEM, user=None)
        services.close_books(clinica_a, ONTEM, user=None)
        with pytest.raises(ValidationError, match="motivo"):
            services.reopen_books(clinica_a, ANTEONTEM, reason=" ", user=None)
        with pytest.raises(ValidationError, match="anterior"):
            services.reopen_books(clinica_a, ONTEM, reason="erro", user=None)
    assert (
        admin.post(
            URL, {"acao": "reabrir", "until": "", "reason": "Lançamento esquecido"}
        ).status_code
        == 302
    )
    with use_clinic(clinica_a):
        assert services.closed_until(clinica_a.pk) is None
        assert BookClosing.objects.count() == 3
    page = admin.get(URL).content.decode()
    assert "Lançamento esquecido" in page and "O financeiro está aberto" in page


def test_each_clinic_has_its_own_closing(clinica_a, clinica_b):
    with use_clinic(clinica_a):
        services.close_books(clinica_a, ONTEM, user=None)
    assert services.closed_until(clinica_b.pk) is None


def test_report_shows_the_closing(clinica_a, admin):
    with use_clinic(clinica_a):
        services.close_books(clinica_a, ONTEM, user=None)
    assert "Financeiro fechado até" in admin.get(reverse("finance:reports")).content.decode()


def test_who_can_see_close_and_reopen(clinica_a, criar_usuario, cliente_de):
    reception = cliente_de(criar_usuario("recepcao_fechamento", clinica_a, Role.FRONT_DESK))
    assert reception.get(URL).status_code == 403
    financeiro = cliente_de(criar_usuario("fin_fechamento", clinica_a, Role.FINANCE))
    assert financeiro.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 302
    assert financeiro.post(URL, {"acao": "outra"}).status_code == 403


def test_demo_only_views(clinica_a, criar_usuario, cliente_de):
    demo = cliente_de(criar_usuario("demo_fechamento", clinica_a, Role.ADMIN, demo=True))
    page = demo.get(URL)
    assert page.status_code == 200 and page.context["fechar_form"] is None
    assert demo.post(URL, {"acao": "fechar", "until": ONTEM.isoformat()}).status_code == 403
    with use_clinic(clinica_a):
        assert not BookClosing.objects.exists()
