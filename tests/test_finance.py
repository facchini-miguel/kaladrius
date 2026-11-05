"""Receivables (0.15.0): installments, payments, receipts, debtors and permissions."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.urls import reverse
from django.utils import timezone, translation

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Role
from apps.finance import services
from apps.finance.models import Category, Entry, FinancialAccount, Installment, Payment
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Maria Devedora", tax_id="52998224725")
        category = Category.objects.get(name="Tratamento")
        cash_register = FinancialAccount.objects.get(name="Caixa")
    return {
        "clinic": clinica_a,
        "patient": patient,
        "category": category,
        "cash_register": cash_register,
        "admin": criar_usuario("admin", clinica_a, Role.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Role.FRONT_DESK),
        "practitioner": criar_usuario("dra", clinica_a, Role.PRACTITIONER),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def new(cenario, **extra):
    return {
        "patient": cenario["patient"].pk,
        "payer": "",
        "description": "Tratamento de canal",
        "category": cenario["category"].pk,
        "practitioner": "",
        "total_amount": "100,00",
        "parcelas": 3,
        "primeiro_vencimento": "2031-01-31",
        "notes": "",
        **extra,
    }


def lancamento_com(cenario, amount="300.00", parcelas=3, due_date=None, patient=True):
    with use_clinic(cenario["clinic"]):
        return services.criar_lancamento(
            clinic=cenario["clinic"],
            kind=Entry.Tipo.RECEBER,
            patient=cenario["patient"] if patient else None,
            payer="" if patient else "João Avulso",
            description="Prótese",
            category=cenario["category"],
            total_amount=Decimal(amount),
            parcelas=parcelas,
            primeiro_vencimento=due_date or HOJE,
            user=cenario["admin"],
        )


def parcelas_de(cenario, entry):
    with use_clinic(cenario["clinic"]):
        return list(Installment.objects.com_saldo().filter(entry=entry).order_by("number"))


# --- Rules -----------------------------------------------------------------------------


def test_divisao_em_parcelas_e_vencimentos_mensais():
    assert services.dividir(Decimal("100.00"), 3) == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert services.somar_meses(datetime.date(2031, 1, 31), 1) == datetime.date(2031, 2, 28)
    assert services.somar_meses(datetime.date(2031, 11, 15), 3) == datetime.date(2032, 2, 15)


def test_clinica_nova_recebe_contas_e_categorias_padrao():
    clinic = Clinic.objects.create(name="Clínica Nova")
    with use_clinic(clinic):
        assert set(FinancialAccount.objects.values_list("name", flat=True)) == {"Caixa", "Banco"}
        assert Category.objects.filter(kind=Category.Tipo.RECEITA).count() == 3
        assert Category.objects.filter(kind=Category.Tipo.DESPESA).count() == 9


def test_moeda_no_formato_do_idioma():
    modelo = Template("{% load formats %}{{ amount|currency }}")
    with translation.override("pt-br"):
        assert modelo.render(Context({"amount": Decimal("1234.5")})) == "R$ 1.234,50"
    with translation.override("en"):
        assert modelo.render(Context({"amount": Decimal("1234.5")})) == "R$ 1,234.50"
    assert modelo.render(Context({"amount": None})) == ""


# --- Entries and payments --------------------------------------------------------------


def test_recepcao_lanca_parcelado(cenario):
    cliente = entrar(cenario, "recepcao")
    response = cliente.post(reverse("finance:entry_new"), new(cenario))
    assert response.status_code == 302
    with use_clinic(cenario["clinic"]):
        entry = Entry.objects.get()
        parcelas = list(entry.parcelas.order_by("number"))
    assert entry.created_by == cenario["recepcao"]
    assert [p.amount for p in parcelas] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert [p.due_date for p in parcelas] == [
        datetime.date(2031, 1, 31),
        datetime.date(2031, 2, 28),
        datetime.date(2031, 3, 31),
    ]


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ({"patient": "", "payer": ""}, "payer"),
        ({"total_amount": "0"}, "total_amount"),
        ({"recebido_agora": "on"}, "method"),
        ({"parcelas": 0}, "parcelas"),
    ],
)
def test_validacoes_do_lancamento(cenario, extra, field):
    response = entrar(cenario, "recepcao").post(reverse("finance:entry_new"), new(cenario, **extra))
    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_pagamento_na_hora_abre_o_recibo(cenario):
    cliente = entrar(cenario, "recepcao")
    response = cliente.post(
        reverse("finance:entry_new"),
        new(
            cenario,
            parcelas=1,
            total_amount="150,50",
            recebido_agora="on",
            method=Payment.Forma.PIX,
            account=cenario["cash_register"].pk,
        ),
        follow=True,
    )
    page = response.content.decode()
    assert "RECIBO" in page and "R$ 150,50" in page and "529.982.247-25" in page
    with use_clinic(cenario["clinic"]):
        assert Installment.objects.abertas().count() == 0


def test_pagamento_parcial_juros_e_saldo(cenario):
    entry = lancamento_com(cenario)
    primeira = parcelas_de(cenario, entry)[0]
    cliente = entrar(cenario, "recepcao")
    url = reverse("finance:receive_installment", args=[primeira.pk])
    data = {"date": HOJE.isoformat(), "method": "dinheiro", "account": cenario["cash_register"].pk}
    # 60 received, 10 of them late fee: the installment goes down by 50.
    assert cliente.post(url, {**data, "amount": "60", "interest": "10"}).status_code == 302
    primeira = parcelas_de(cenario, entry)[0]
    assert (primeira.pago, primeira.balance) == (Decimal("50.00"), Decimal("50.00"))
    assert services.status(primeira)[0] == "parcial"
    # Paying more than what is left is refused.
    response = cliente.post(url, {**data, "amount": "50,01"})
    assert "passa do que falta" in response.content.decode()
    cliente.post(url, {**data, "amount": "50"})
    assert parcelas_de(cenario, entry)[0].balance == 0


def test_desconto_so_para_o_administrador(cenario):
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    url = reverse("finance:receive_installment", args=[installment.pk])
    data = {"date": HOJE.isoformat(), "method": "pix", "account": cenario["cash_register"].pk}

    reception = entrar(cenario, "recepcao")
    assert "discount" not in reception.get(url).context["form"].fields
    reception.post(url, {**data, "amount": "90", "discount": "10"})  # discount ignored
    assert parcelas_de(cenario, entry)[0].balance == Decimal("10.00")

    admin = entrar(cenario, "admin")
    admin.post(url, {**data, "amount": "5", "discount": "5"})
    assert parcelas_de(cenario, entry)[0].balance == 0


def test_estorno_e_cancelamento_so_do_administrador(cenario):
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    installment = parcelas_de(cenario, entry)[0]
    with use_clinic(cenario["clinic"]):
        payment = services.receber(
            installment,
            user=cenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=cenario["cash_register"],
        )
    reception = entrar(cenario, "recepcao")
    estornar = reverse("finance:reverse_payment", args=[payment.pk])
    cancelar = reverse("finance:cancel", args=[entry.pk])
    assert reception.post(estornar, {"reason": "x"}).status_code == 403
    assert reception.post(cancelar, {"reason": "x"}).status_code == 403

    admin = entrar(cenario, "admin")
    # With an active payment the entry cannot be cancelled.
    response = admin.post(cancelar, {"reason": "Desistiu"}, follow=True)
    assert "Estorne os pagamentos" in response.content.decode()
    # The page names the payment with the amount in reais (review stage 5: it read "100.00").
    assert "R$ 100,00" in admin.get(estornar).content.decode()
    admin.post(estornar, {"reason": "Pix devolvido"})
    payment.refresh_from_db()
    assert payment.reversed and payment.reversed_by == cenario["admin"]
    assert parcelas_de(cenario, entry)[0].balance == Decimal("100.00")
    assert "ESTORNADO" in admin.get(reverse("finance:receipt", args=[payment.pk])).content.decode()

    admin.post(cancelar, {"reason": "Desistiu do tratamento"})
    entry.refresh_from_db()
    assert entry.cancelled and entry.cancellation_reason == "Desistiu do tratamento"
    # A second click (or a stale page) changes nothing.
    with use_clinic(cenario["clinic"]), pytest.raises(ValidationError):
        services.cancelar(entry, reason="De novo", user=cenario["admin"])
    with use_clinic(cenario["clinic"]), pytest.raises(ValidationError):
        services.estornar(payment, reason="De novo", user=cenario["admin"])
    entry.refresh_from_db()
    payment.refresh_from_db()
    assert entry.cancellation_reason == "Desistiu do tratamento"
    assert payment.reversal_reason == "Pix devolvido"
    with use_clinic(cenario["clinic"]):
        assert not Installment.objects.abertas().exists()


def test_devedores_por_tempo_de_atraso(cenario):
    lancamento_com(
        cenario, amount="200.00", parcelas=2, due_date=HOJE - datetime.timedelta(days=45)
    )
    lancamento_com(
        cenario,
        amount="70.00",
        parcelas=1,
        due_date=HOJE - datetime.timedelta(days=100),
        patient=False,
    )
    with use_clinic(cenario["clinic"]):
        rows = services.devedores()
    assert [row["name"] for row in rows] == ["Maria Devedora", "João Avulso"]
    maria, joao = rows
    # 45 days late (31-60) and the next one 15 days late (up to 30).
    assert maria["faixas"] == [Decimal("100.00"), Decimal("100.00"), 0, 0]
    assert maria["vencido"] == Decimal("200.00")
    assert joao["faixas"][3] == Decimal("70.00")
    page = entrar(cenario, "recepcao").get(reverse("finance:debtors")).content.decode()
    assert "Maria Devedora" in page and "R$ 270,00" in page


def test_lista_a_receber_e_filtros(cenario):
    lancamento_com(cenario, amount="90.00", parcelas=3, due_date=HOJE - datetime.timedelta(days=40))
    cliente = entrar(cenario, "recepcao")
    results = reverse("finance:receivables")
    assert len(cliente.get(results).context["pagina"]) == 3
    assert len(cliente.get(results, {"status": "vencidas"}).context["pagina"]) == 2
    assert len(cliente.get(results, {"q": "devedora"}).context["pagina"]) == 3
    assert len(cliente.get(results, {"q": "ninguem"}).context["pagina"]) == 0


def test_ficha_mostra_o_financeiro_do_paciente(cenario):
    lancamento_com(cenario, amount="80.00", parcelas=2, due_date=HOJE - datetime.timedelta(days=5))
    url = reverse("patients:record", args=[cenario["patient"].pk])
    response = entrar(cenario, "recepcao").get(url)
    financeiro = response.context["financeiro"]
    assert (financeiro["vencido"], financeiro["a_vencer"]) == (Decimal("40.00"), Decimal("40.00"))
    # Practitioners do not see the finances.
    assert "financeiro" not in entrar(cenario, "practitioner").get(url).context


# --- Permissions, isolation, records -----------------------------------------------------


def test_profissional_nao_acessa_o_financeiro(cenario):
    cliente = entrar(cenario, "practitioner")
    assert cliente.get(reverse("finance:receivables")).status_code == 403
    assert cliente.get(reverse("finance:debtors")).status_code == 403
    assert reverse("finance:receivables") not in cliente.get(reverse("home")).content.decode()


def test_recepcao_nao_mexe_em_categorias_e_contas(cenario):
    cliente = entrar(cenario, "recepcao")
    assert cliente.get(reverse("finance:catalog", args=["categories"])).status_code == 403
    assert cliente.get(reverse("finance:catalog_new", args=["accounts"])).status_code == 403


def test_admin_cadastra_categorias_e_contas(cenario):
    cliente = entrar(cenario, "admin")
    url = reverse("finance:catalog_new", args=["categories"])
    assert (
        cliente.post(url, {"name": "Ortodontia", "kind": "receita", "active": "on"}).status_code
        == 302
    )
    response = cliente.post(url, {"name": "Ortodontia", "kind": "receita", "active": "on"})
    assert "Já existe" in response.content.decode()
    cliente.post(
        reverse("finance:catalog_new", args=["accounts"]),
        {"name": "Maquininha", "kind": "cartao", "active": "on"},
    )
    with use_clinic(cenario["clinic"]):
        assert Category.objects.filter(name="Ortodontia").exists()
        assert FinancialAccount.objects.filter(name="Maquininha", kind="cartao").exists()
    assert cliente.get("/finance/something-else/").status_code == 404


def test_lancamento_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    entry = lancamento_com(cenario)
    other = cliente_de(criar_usuario("admin_b", clinica_b, Role.ADMIN))
    assert other.get(reverse("finance:entry", args=[entry.pk])).status_code == 404
    assert other.get(reverse("finance:receivables")).context["pagina"].paginator.count == 0


def test_exclusao_definitiva_mantem_o_lancamento_sem_o_paciente(cenario):
    entry = lancamento_com(cenario)
    with use_clinic(cenario["clinic"]):
        Entry.objects.filter(pk=entry.pk).update(notes="Mãe: Joana, 9999-0000")
        payment = services.receber(
            entry.parcelas.first(),
            user=cenario["admin"],
            amount=Decimal("10.00"),
            method="pix",
            account=FinancialAccount.objects.get(name="Caixa"),
            note="Pago pela Joana",
        )
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    admin = entrar(cenario, "admin")
    admin.post(reverse("patients:delete", args=[cenario["patient"].pk]))
    entry.refresh_from_db()
    payment.refresh_from_db()
    assert entry.patient is None
    assert entry.payer == f"Paciente excluído (código {cenario['patient'].pk})"
    # Notes may hold personal data; amounts stay.
    assert (entry.notes, payment.note) == ("", "")
    assert payment.amount == Decimal("10.00")


# --- Payables, cash flow and reports (0.16.0) ---------------------------------------------


def despesa(cenario, **extra):
    with use_clinic(cenario["clinic"]):
        aluguel = Category.objects.get(name="Aluguel")
    return {
        "payer": "Imobiliária",
        "description": "Aluguel",
        "category": aluguel.pk,
        "amount": "3.000,00".replace(".", ""),
        "modo": "repetir",
        "parcelas": 12,
        "primeiro_vencimento": "2031-01-10",
        "notes": "",
        **extra,
    }


def test_despesa_fixa_mensal_e_parcelada(cenario):
    admin = entrar(cenario, "admin")
    assert admin.post(reverse("finance:expense_new"), despesa(cenario)).status_code == 302
    admin.post(
        reverse("finance:expense_new"),
        despesa(cenario, description="Cadeira", modo="dividir", amount="900", parcelas=3),
    )
    with use_clinic(cenario["clinic"]):
        aluguel = Entry.objects.get(description="Aluguel")
        cadeira = Entry.objects.get(description="Cadeira")
        assert aluguel.kind == Entry.Tipo.PAGAR
        assert aluguel.total_amount == Decimal("36000.00")
        assert {p.amount for p in aluguel.parcelas.all()} == {Decimal("3000.00")}
        assert aluguel.parcelas.count() == 12
        assert [p.amount for p in cadeira.parcelas.order_by("number")] == [Decimal("300.00")] * 3


def test_despesa_paga_na_hora_e_pagamento_de_parcela(cenario):
    admin = entrar(cenario, "admin")
    admin.post(
        reverse("finance:expense_new"),
        despesa(
            cenario, parcelas=2, pago_agora="on", method="pix", account=cenario["cash_register"].pk
        ),
    )
    with use_clinic(cenario["clinic"]):
        entry = Entry.objects.get()
    segunda = parcelas_de(cenario, entry)[1]
    response = admin.post(
        reverse("finance:receive_installment", args=[segunda.pk]),
        {
            "date": HOJE.isoformat(),
            "amount": "3000",
            "method": "boleto",
            "account": cenario["cash_register"].pk,
        },
    )
    # Paying a bill goes back to the entry (receipts are only for money received).
    assert response.url == reverse("finance:entry", args=[entry.pk])
    assert all(p.balance == 0 for p in parcelas_de(cenario, entry))


def test_recepcao_nao_ve_contas_a_pagar(cenario):
    admin = entrar(cenario, "admin")
    admin.post(reverse("finance:expense_new"), despesa(cenario, parcelas=1))
    with use_clinic(cenario["clinic"]):
        entry = Entry.objects.get()
        installment = entry.parcelas.get()
    reception = entrar(cenario, "recepcao")
    for url in (
        reverse("finance:payables"),
        reverse("finance:expense_new"),
        reverse("finance:cash_flow"),
        reverse("finance:reports"),
        reverse("finance:entry", args=[entry.pk]),
        reverse("finance:receive_installment", args=[installment.pk]),
    ):
        assert reception.get(url).status_code == 403, url
    assert reverse("finance:payables") not in reception.get(reverse("home")).content.decode()


def test_saldo_das_contas_com_saldo_inicial(cenario):
    with use_clinic(cenario["clinic"]):
        FinancialAccount.objects.filter(pk=cenario["cash_register"].pk).update(
            opening_balance=Decimal("-50.00")
        )
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    with use_clinic(cenario["clinic"]):
        services.receber(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="dinheiro",
            account=cenario["cash_register"],
        )
        saldos = dict((account.name, balance) for account, balance in services.saldos_das_contas())
    assert saldos == {"Caixa": Decimal("50.00"), "Banco": Decimal("0.00")}
    # A negative initial balance is accepted in the form (overdrawn bank).
    admin = entrar(cenario, "admin")
    response = admin.post(
        reverse("finance:catalog_edit", args=["accounts", cenario["cash_register"].pk]),
        {"name": "Caixa", "kind": "dinheiro", "opening_balance": "-10,50", "active": "on"},
    )
    assert response.status_code == 302


def test_fluxo_de_caixa_realizado_e_previsto(cenario):
    since = datetime.date(2031, 3, 1)
    until = datetime.date(2031, 3, 31)
    recebivel = lancamento_com(
        cenario, amount="200.00", parcelas=2, due_date=datetime.date(2031, 3, 5)
    )
    with use_clinic(cenario["clinic"]):
        FinancialAccount.objects.filter(pk=cenario["cash_register"].pk).update(
            opening_balance=Decimal("1000.00")
        )
        services.receber(
            parcelas_de(cenario, recebivel)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=cenario["cash_register"],
            date=datetime.date(2031, 3, 5),
        )
        aluguel = services.criar_lancamento(
            clinic=cenario["clinic"],
            kind=Entry.Tipo.PAGAR,
            payer="Imobiliária",
            description="Aluguel",
            category=Category.objects.get(name="Aluguel"),
            total_amount=Decimal("300.00"),
            parcelas=1,
            primeiro_vencimento=datetime.date(2031, 3, 10),
            user=cenario["admin"],
        )
        fluxo = services.fluxo_de_caixa(since, until, today=datetime.date(2031, 3, 1))
    assert fluxo["opening_balance"] == Decimal("1000.00")
    rows = {row["date"]: row for row in fluxo["linhas"]}
    assert rows[datetime.date(2031, 3, 5)]["entradas"] == Decimal("100.00")
    assert rows[datetime.date(2031, 3, 10)]["saidas_previstas"] == Decimal("300.00")
    # 2nd receivable installment due 2031-04-05: outside the period.
    assert fluxo["saldo_final"] == Decimal("800.00")
    assert aluguel.total_amount == Decimal("300.00")
    response = entrar(cenario, "admin").get(
        reverse("finance:cash_flow"), {"de": "2031-03-01", "until": "2031-03-31", "agrupar": "mes"}
    )
    assert response.status_code == 200 and response.context["por_mes"]


def test_relatorio_por_forma_categoria_e_profissional(cenario):
    entry = lancamento_com(cenario, amount="100.00", parcelas=1)
    with use_clinic(cenario["clinic"]):
        payment = services.receber(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="pix",
            account=cenario["cash_register"],
        )
        relatorio = services.relatorio(HOJE, HOJE)
    assert relatorio["por_forma"] == [("Pix", Decimal("100.00"))]
    assert relatorio["por_categoria"] == [("Tratamento", Decimal("100.00"))]
    assert relatorio["resultado"] == Decimal("100.00")
    # Reversed payments leave the reports.
    with use_clinic(cenario["clinic"]):
        services.estornar(payment, reason="erro", user=cenario["admin"])
        assert services.relatorio(HOJE, HOJE)["total_recebido"] == 0
    assert (
        entrar(cenario, "admin").get(reverse("finance:reports"), {"de": "lixo"}).status_code == 200
    )


def test_listas_de_escolha_sem_texto_em_ingles(cenario):
    page = entrar(cenario, "admin").get(reverse("finance:expense_new")).content.decode()
    assert "Select an option" not in page


# --- Daily cash drawer (0.17.0) -----------------------------------------------------------


def test_caixa_do_dia_completo(cenario):
    from apps.finance.models import CashMovement, CashRegister

    with use_clinic(cenario["clinic"]):
        bank = FinancialAccount.objects.get(name="Banco")
    reception = entrar(cenario, "recepcao")
    assert reception.get(reverse("finance:cash")).status_code == 200
    response = reception.post(reverse("finance:cash"), {"amount": "100,00"})
    with use_clinic(cenario["clinic"]):
        cash_register = CashRegister.objects.get()
    assert response.url == reverse("finance:cash_detail", args=[cash_register.pk])
    # Only one open drawer per account: the page goes straight to it.
    assert reception.get(reverse("finance:cash")).url == response.url

    # A cash payment while the drawer is open enters it; a Pix into the bank does not.
    entry = lancamento_com(cenario, amount="80.00", parcelas=2)
    primeira, segunda = parcelas_de(cenario, entry)
    with use_clinic(cenario["clinic"]):
        services.receber(
            primeira,
            user=cenario["recepcao"],
            amount=Decimal("40"),
            method="dinheiro",
            account=cenario["cash_register"],
        )
        services.receber(
            segunda, user=cenario["recepcao"], amount=Decimal("40"), method="pix", account=bank
        )

    url = lambda name, *args: reverse(f"finance:{name}", args=[cash_register.pk, *args])  # noqa: E731
    reception.post(url("cash_movement", "top-up"), {"amount": "10", "reason": "Troco"})
    reception.post(
        url("cash_movement", "withdrawal"),
        {"amount": "120", "reason": "Depósito", "other_account": bank.pk},
    )
    # A withdrawal larger than what should be in the drawer is refused.
    response = reception.post(url("cash_movement", "withdrawal"), {"amount": "999", "reason": "x"})
    assert "passa do valor" in response.content.decode()

    with use_clinic(cenario["clinic"]):
        summary = services.resumo_do_caixa(cash_register)
        saldos = dict((c.name, s) for c, s in services.saldos_das_contas())
    assert (summary["entradas"], summary["reforcos"], summary["retiradas"]) == (
        Decimal("40.00"),
        Decimal("10.00"),
        Decimal("120.00"),
    )
    assert summary["esperado"] == Decimal("30.00")  # 100 + 40 + 10 - 120
    # The deposit moved money from the drawer account to the bank.
    assert saldos == {"Caixa": Decimal("-70.00"), "Banco": Decimal("160.00")}

    reception.post(url("cash_close"), {"counted_amount": "28,50", "note": "Faltou troco"})
    cash_register.refresh_from_db()
    assert not cash_register.aberto and cash_register.closed_by == cenario["recepcao"]
    assert (
        cash_register.expected_amount,
        cash_register.counted_amount,
        cash_register.diferenca,
    ) == (
        Decimal("30.00"),
        Decimal("28.50"),
        Decimal("-1.50"),
    )
    # Closed: no more movements, and a new drawer can be opened.
    assert reception.get(url("cash_close")).status_code == 404
    assert reception.get(url("cash_movement", "other")).status_code == 404
    reception.post(reverse("finance:cash"), {"amount": "28,50"})
    with use_clinic(cenario["clinic"]):
        assert CashRegister.objects.filter(closed_at__isnull=True).count() == 1
        assert CashMovement.objects.count() == 2


def test_profissional_nao_opera_o_caixa(cenario):
    assert entrar(cenario, "practitioner").get(reverse("finance:cash")).status_code == 403


def test_caixa_fechado_nao_muda_com_estorno_posterior(cenario):
    with use_clinic(cenario["clinic"]):
        cash_register = services.abrir_caixa(
            cenario["cash_register"], amount=Decimal("0"), user=cenario["admin"]
        )
    entry = lancamento_com(cenario, amount="50.00", parcelas=1)
    with use_clinic(cenario["clinic"]):
        payment = services.receber(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("50"),
            method="dinheiro",
            account=cenario["cash_register"],
        )
        services.fechar_caixa(
            cash_register, counted_amount=Decimal("50"), note="", user=cenario["admin"]
        )
        services.estornar(payment, reason="erro", user=cenario["admin"])
        cash_register.refresh_from_db()
    assert (cash_register.expected_amount, cash_register.diferenca) == (Decimal("50.00"), 0)


@pytest.mark.parametrize("digitado", ["1.500,00", "R$ 1.500,00", "1500,00", "1.500"])
def test_valor_com_ponto_de_milhar(cenario, digitado):
    """Review stage 3: "1.500,00", as people write it, was refused ("Informe um número")."""
    response = entrar(cenario, "admin").post(
        reverse("finance:entry_new"), new(cenario, total_amount=digitado, parcelas=1)
    )
    assert response.status_code == 302, response.context["form"].errors
    with use_clinic(cenario["clinic"]):
        assert Entry.objects.get().total_amount == Decimal("1500.00")


def test_cheque_nao_e_mais_oferecido(cenario):
    """The owner: cheques are not used anymore. A cheque recorded before keeps its name."""
    entry = lancamento_com(cenario)
    installment = parcelas_de(cenario, entry)[0]
    admin = entrar(cenario, "admin")
    for url in (
        reverse("finance:receive_installment", args=[installment.pk]),
        reverse("finance:entry_new"),
        reverse("finance:expense_new"),
    ):
        page = admin.get(url).content.decode()
        assert 'value="pix"' in page and 'value="cheque"' not in page, url
    recusado = admin.post(
        reverse("finance:receive_installment", args=[installment.pk]),
        {
            "date": "2026-10-30",
            "amount": "100,00",
            "method": "cheque",
            "account": cenario["cash_register"].pk,
        },
    )
    assert "method" in recusado.context["form"].errors
    with use_clinic(cenario["clinic"]):
        old = services.receber(
            installment,
            user=cenario["admin"],
            amount=Decimal("100"),
            method="cheque",
            account=cenario["cash_register"],
        )
    assert old.get_method_display() == "Cheque"


def test_devedores_paginados_e_com_busca(cenario):
    """Volume test: thousands of debtors filled a single page of several MB."""
    with use_clinic(cenario["clinic"]):
        for n in range(55):
            services.criar_lancamento(
                clinic=cenario["clinic"],
                kind=Entry.Tipo.RECEBER,
                payer=f"Pagador Fictício {n:02d}",
                description="Consulta",
                category=cenario["category"],
                total_amount=Decimal("10"),
                parcelas=1,
                primeiro_vencimento=HOJE - datetime.timedelta(days=10),
                user=cenario["admin"],
            )
    cliente = entrar(cenario, "recepcao")
    primeira = cliente.get(reverse("finance:debtors")).content.decode()
    assert "55 devedores" in primeira and "Página 1 de 2" in primeira
    assert "R$ 550,00" in primeira  # the totals still add up everyone
    search = cliente.get(reverse("finance:debtors"), {"q": "fictício 07"}).content.decode()
    assert "Pagador Fictício 07" in search and "Pagador Fictício 08" not in search
