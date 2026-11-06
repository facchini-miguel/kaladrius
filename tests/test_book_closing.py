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

TODAY = timezone.localdate()
YESTERDAY = TODAY - datetime.timedelta(days=1)
DAY_BEFORE_YESTERDAY = TODAY - datetime.timedelta(days=2)
URL = reverse("finance:closing")


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_fechamento", clinic_a, Role.ADMIN))


@pytest.fixture
def installment(clinic_a):
    with use_clinic(clinic_a):
        entry = services.create_entry(
            clinic=clinic_a,
            kind=Entry.Kind.RECEIVABLE,
            payer="Pagador fictício",
            description="Consulta",
            category=Category.objects.get(name="Consulta"),
            total_amount=Decimal("300"),
            parcelas=1,
            primeiro_vencimento=DAY_BEFORE_YESTERDAY,
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


def test_closing_locks_payments_and_reversals_in_the_period(clinic_a, installment, admin):
    old = receive(clinic_a, installment, DAY_BEFORE_YESTERDAY)
    assert admin.post(URL, {"action": "fechar", "until": YESTERDAY.isoformat()}).status_code == 302
    with use_clinic(clinic_a):
        assert services.closed_until(clinic_a.pk) == YESTERDAY
    with pytest.raises(ValidationError, match="fechado"):
        receive(clinic_a, installment, YESTERDAY)
    with use_clinic(clinic_a), pytest.raises(ValidationError, match="fechado"):
        services.reverse_payment(old, reason="erro", user=None)
    # Today is never closed: money keeps coming in.
    assert receive(clinic_a, installment, TODAY).pk


def test_receiving_on_screen_shows_the_error(clinic_a, installment, admin):
    with use_clinic(clinic_a):
        services.close_books(clinic_a, YESTERDAY, user=None)
    response = admin.post(
        reverse("finance:receive_installment", args=[installment.pk]),
        {
            "date": YESTERDAY.isoformat(),
            "amount": "100",
            "method": "pix",
            "account": FinancialAccount.all_objects.get(clinic=clinic_a, name="Caixa").pk,
        },
        follow=True,
    )
    assert "fechado até" in response.content.decode()


@pytest.mark.parametrize(
    ("until", "message"),
    [(TODAY, "ontem"), (TODAY + datetime.timedelta(days=3), "ontem")],
)
def test_does_not_close_today_or_the_future(clinic_a, until, message):
    with use_clinic(clinic_a), pytest.raises(ValidationError, match=message):
        services.close_books(clinic_a, until, user=None)


def test_close_again_only_forward_and_reopen_with_reason(clinic_a, admin):
    with use_clinic(clinic_a):
        services.close_books(clinic_a, DAY_BEFORE_YESTERDAY, user=None)
        with pytest.raises(ValidationError, match="já está fechado"):
            services.close_books(clinic_a, DAY_BEFORE_YESTERDAY, user=None)
        services.close_books(clinic_a, YESTERDAY, user=None)
        with pytest.raises(ValidationError, match="motivo"):
            services.reopen_books(clinic_a, DAY_BEFORE_YESTERDAY, reason=" ", user=None)
        with pytest.raises(ValidationError, match="anterior"):
            services.reopen_books(clinic_a, YESTERDAY, reason="erro", user=None)
    assert (
        admin.post(
            URL, {"action": "reabrir", "until": "", "reason": "Lançamento esquecido"}
        ).status_code
        == 302
    )
    with use_clinic(clinic_a):
        assert services.closed_until(clinic_a.pk) is None
        assert BookClosing.objects.count() == 3
    page = admin.get(URL).content.decode()
    assert "Lançamento esquecido" in page and "O financeiro está aberto" in page


def test_each_clinic_has_its_own_closing(clinic_a, clinic_b):
    with use_clinic(clinic_a):
        services.close_books(clinic_a, YESTERDAY, user=None)
    assert services.closed_until(clinic_b.pk) is None


def test_report_shows_the_closing(clinic_a, admin):
    with use_clinic(clinic_a):
        services.close_books(clinic_a, YESTERDAY, user=None)
    assert "Financeiro fechado até" in admin.get(reverse("finance:reports")).content.decode()


def test_who_can_see_close_and_reopen(clinic_a, create_user, client_for):
    reception = client_for(create_user("recepcao_fechamento", clinic_a, Role.FRONT_DESK))
    assert reception.get(URL).status_code == 403
    finance_user = client_for(create_user("fin_fechamento", clinic_a, Role.FINANCE))
    assert (
        finance_user.post(URL, {"action": "fechar", "until": YESTERDAY.isoformat()}).status_code
        == 302
    )
    assert finance_user.post(URL, {"action": "outra"}).status_code == 403


def test_demo_only_views(clinic_a, create_user, client_for):
    demo = client_for(create_user("demo_fechamento", clinic_a, Role.ADMIN, demo=True))
    page = demo.get(URL)
    assert page.status_code == 200 and page.context["close_form"] is None
    assert demo.post(URL, {"action": "fechar", "until": YESTERDAY.isoformat()}).status_code == 403
    with use_clinic(clinic_a):
        assert not BookClosing.objects.exists()
