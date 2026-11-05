"""Practitioner commission (0.19.0): percentage of what is received, paid once."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.finance import commissions, services
from apps.finance.models import Category, Commission, Entry, FinancialAccount, Payment
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

pytestmark = pytest.mark.django_db
HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    admin = criar_usuario("admin", clinica_a, Papel.ADMIN)
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Paulo Paciente")
        dra = Practitioner.objects.create(name="Dra. Ana", commission_percentage=Decimal("40"))
        dr = Practitioner.objects.create(name="Dr. Beto")
        tratamento = Category.objects.get(name="Tratamento")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        category = Category.objects.get(name="Comissões")
    return {
        "clinic": clinica_a,
        "patient": patient,
        "dra": dra,
        "dr": dr,
        "tratamento": tratamento,
        "cash_register": cash_register,
        "category": category,
        "admin": admin,
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        # The test client is shared: log in as the administrator by default.
        "cliente": cliente_de(admin),
        "cliente_de": cliente_de,
    }


def receber(cenario, amount, practitioner, date=ONTEM, interest="0"):
    """A receivable for `valor` paid in full on `data`."""
    with usar_clinica(cenario["clinic"]):
        entry = services.criar_lancamento(
            clinic=cenario["clinic"],
            kind=Entry.Tipo.RECEBER,
            patient=cenario["patient"],
            practitioner=practitioner,
            description="Tratamento",
            category=cenario["tratamento"],
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=cenario["admin"],
        )
        return services.receber(
            entry.parcelas.get(),
            user=cenario["admin"],
            amount=Decimal(amount) + Decimal(interest),
            interest=Decimal(interest),
            method="pix",
            account=cenario["cash_register"],
            date=date,
        )


def pagar_comissao(cenario, practitioner, until=HOJE):
    return cenario["cliente"].post(
        f"{reverse('finance:commission_pay', args=[practitioner.pk])}?until={until.isoformat()}",
        {"due_date": HOJE.isoformat(), "category": cenario["category"].pk},
    )


def test_calculo_inclui_juros_e_ignora_outros_profissionais(cenario):
    receber(cenario, "100.00", cenario["dra"], interest="10.00")
    receber(cenario, "250.55", cenario["dra"])
    receber(cenario, "999.00", cenario["dr"])  # other practitioner
    receber(cenario, "500.00", None)  # no practitioner: no commission
    receber(cenario, "80.00", cenario["dra"], date=HOJE)  # after the cut-off date
    with usar_clinica(cenario["clinic"]):
        calculo = commissions.pendente(cenario["dra"], ONTEM)
    assert calculo["received_amount"] == Decimal("360.55")
    assert calculo["amount"] == Decimal("144.22")  # 40% of 360.55, rounded half up


def test_pagar_cria_despesa_e_nao_paga_duas_vezes(cenario):
    receber(cenario, "300.00", cenario["dra"])
    response = pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        commission = Commission.objects.get()
        entry = commission.entry
        assert response.url == reverse("finance:entry", args=[entry.pk])
        assert (entry.kind, entry.total_amount, entry.payer) == (
            Entry.Tipo.PAGAR,
            Decimal("120.00"),
            "Dra. Ana",
        )
        assert entry.category.name == "Comissões"
        assert Payment.objects.get().commission == commission
        assert commissions.pendente(cenario["dra"], HOJE)["amount"] == 0
    # Paying again finds nothing.
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        assert Commission.objects.count() == 1
    # Only new receipts make up the next one.
    receber(cenario, "50.00", cenario["dra"], date=HOJE)
    with usar_clinica(cenario["clinic"]):
        assert commissions.pendente(cenario["dra"], HOJE)["amount"] == Decimal("20.00")


def test_estorno_depois_de_pago_e_descontado_no_proximo(cenario):
    payment = receber(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    # The percentage changes, but the deduction uses the one it was paid with (40%).
    with usar_clinica(cenario["clinic"]):
        Practitioner.objects.filter(pk=cenario["dra"].pk).update(commission_percentage=10)
        cenario["dra"].refresh_from_db()
        services.estornar(payment, reason="Pix devolvido", user=cenario["admin"])
    receber(cenario, "1000.00", cenario["dra"], date=HOJE)
    with usar_clinica(cenario["clinic"]):
        calculo = commissions.pendente(cenario["dra"], HOJE)
        assert (calculo["bruta"], calculo["reversal_deduction"], calculo["amount"]) == (
            Decimal("100.00"),
            Decimal("120.00"),
            Decimal("-20.00"),
        )
        # The list adds up in the database (volume test) and must agree with the detail.
        row = next(x for x in commissions.summary(HOJE) if x["practitioner"] == cenario["dra"])
        chaves = ("received_amount", "bruta", "reversal_deduction", "amount")
        assert [row[c] for c in chaves] == [calculo[c] for c in chaves]
    # Nothing to pay while the deduction is larger: it waits for more receipts.
    pagar_comissao(cenario, cenario["dra"])
    receber(cenario, "500.00", cenario["dra"], date=HOJE)
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        segunda = Commission.objects.latest("pk")
        assert (segunda.bruta, segunda.reversal_deduction, segunda.amount) == (
            Decimal("150.00"),
            Decimal("120.00"),
            Decimal("30.00"),
        )
        payment.refresh_from_db()
        assert payment.commission_reversal == segunda
    extrato = cenario["cliente"].get(reverse("finance:commission", args=[segunda.pk]))
    assert "Pix devolvido" not in extrato.content.decode()  # reasons are not on the statement
    assert list(extrato.context["reversal_deduction"]) == [payment]


def test_cancelar_a_despesa_desfaz_a_comissao(cenario):
    receber(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        commission = Commission.objects.get()
    cenario["cliente"].post(
        reverse("finance:cancel", args=[commission.entry_id]), {"reason": "Errado"}
    )
    commission.refresh_from_db()
    assert commission.cancelled
    with usar_clinica(cenario["clinic"]):
        assert not Payment.objects.filter(commission__isnull=False).exists()
        assert commissions.pendente(cenario["dra"], HOJE)["amount"] == Decimal("120.00")


def test_telas_e_percentual(cenario):
    receber(cenario, "300.00", cenario["dra"])
    cliente = cenario["cliente"]
    page = cliente.get(reverse("finance:commissions"))
    assert [row["practitioner"] for row in page.context["linhas"]] == [cenario["dra"]]
    assert list(page.context["sem_percentual"]) == [cenario["dr"]]
    assert "R$ 120,00" in page.content.decode()
    url = reverse("finance:commission_percentage", args=[cenario["dr"].pk])
    assert cliente.post(url, {"commission_percentage": "101"}).status_code == 200  # > 100
    cliente.post(url, {"commission_percentage": "35,5"})
    cenario["dr"].refresh_from_db()
    assert cenario["dr"].commission_percentage == Decimal("35.50")
    pagar = cliente.get(reverse("finance:commission_pay", args=[cenario["dra"].pk]))
    assert pagar.context["calculo"]["amount"] == Decimal("120.00")
    # A future cut-off date is not allowed: it becomes today.
    futuro = (HOJE + datetime.timedelta(days=30)).isoformat()
    assert cliente.get(reverse("finance:commissions"), {"until": futuro}).context["until"] == HOJE


def test_so_o_administrador(cenario):
    reception = cenario["cliente_de"](cenario["recepcao"])
    assert reception.get(reverse("finance:commissions")).status_code == 403
    assert (
        reception.post(reverse("finance:commission_pay", args=[cenario["dra"].pk])).status_code
        == 403
    )
    assert (
        reception.post(
            reverse("finance:commission_percentage", args=[cenario["dra"].pk]),
            {"commission_percentage": "90"},
        ).status_code
        == 403
    )


def test_profissional_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    other = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert other.get(reverse("finance:commission_pay", args=[cenario["dra"].pk])).status_code == 404


def test_nao_cancela_comissao_cujo_estorno_ja_foi_descontado_em_outra(cenario):
    """Cancelling C1 after C2 deducted a reversal of C1 would lose that amount for good."""
    payment = receber(cenario, "100.00", cenario["dra"])  # 40.00 in C1
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        primeira = Commission.objects.get()
        services.estornar(payment, reason="Pix devolvido", user=cenario["admin"])
    receber(cenario, "300.00", cenario["dra"], date=HOJE)  # 120.00 - 40.00 in C2
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinic"]):
        segunda = Commission.objects.exclude(pk=primeira.pk).get()
    cancelar = reverse("finance:cancel", args=[primeira.entry_id])
    response = cenario["cliente"].post(cancelar, {"reason": "Errado"}, follow=True)
    assert "Cancele aquela antes" in response.content.decode()
    primeira.refresh_from_db()
    payment.refresh_from_db()
    assert not primeira.cancelled and not primeira.entry.cancelled
    assert (payment.commission, payment.commission_reversal) == (primeira, segunda)
    # In the right order both go, and everything is pending again.
    cenario["cliente"].post(
        reverse("finance:cancel", args=[segunda.entry_id]), {"reason": "Errado"}
    )
    cenario["cliente"].post(cancelar, {"reason": "Errado"})
    primeira.refresh_from_db()
    assert primeira.cancelled
    with usar_clinica(cenario["clinic"]):
        assert commissions.pendente(cenario["dra"], HOJE)["amount"] == Decimal("120.00")
