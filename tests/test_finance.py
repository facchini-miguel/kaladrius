"""Receivables (0.15.0): installments, payments, receipts, debtors and permissions."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.urls import reverse
from django.utils import timezone, translation

from apps.core.isolation import usar_clinica
from apps.core.models import Clinic, Papel
from apps.finance import services
from apps.finance.models import Category, Entry, FinancialAccount, Installment, Payment
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(nome="Maria Devedora", cpf_cnpj="52998224725")
        categoria = Category.objects.get(nome="Tratamento")
        caixa = FinancialAccount.objects.get(nome="Caixa")
    return {
        "clinic": clinica_a,
        "patient": patient,
        "categoria": categoria,
        "caixa": caixa,
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "practitioner": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def novo(cenario, **extra):
    return {
        "patient": cenario["patient"].pk,
        "pessoa": "",
        "descricao": "Tratamento de canal",
        "categoria": cenario["categoria"].pk,
        "practitioner": "",
        "valor_total": "100,00",
        "parcelas": 3,
        "primeiro_vencimento": "2031-01-31",
        "observacoes": "",
        **extra,
    }


def lancamento_com(cenario, valor="300.00", parcelas=3, vencimento=None, patient=True):
    with usar_clinica(cenario["clinic"]):
        return services.criar_lancamento(
            clinic=cenario["clinic"],
            tipo=Entry.Tipo.RECEBER,
            patient=cenario["patient"] if patient else None,
            pessoa="" if patient else "João Avulso",
            descricao="Prótese",
            categoria=cenario["categoria"],
            valor_total=Decimal(valor),
            parcelas=parcelas,
            primeiro_vencimento=vencimento or HOJE,
            user=cenario["admin"],
        )


def parcelas_de(cenario, lancamento):
    with usar_clinica(cenario["clinic"]):
        return list(
            Installment.objects.com_saldo().filter(lancamento=lancamento).order_by("numero")
        )


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
    clinic = Clinic.objects.create(nome="Clínica Nova")
    with usar_clinica(clinic):
        assert set(FinancialAccount.objects.values_list("nome", flat=True)) == {"Caixa", "Banco"}
        assert Category.objects.filter(tipo=Category.Tipo.RECEITA).count() == 3
        assert Category.objects.filter(tipo=Category.Tipo.DESPESA).count() == 9


def test_moeda_no_formato_do_idioma():
    modelo = Template("{% load formats %}{{ valor|moeda }}")
    with translation.override("pt-br"):
        assert modelo.render(Context({"valor": Decimal("1234.5")})) == "R$ 1.234,50"
    with translation.override("en"):
        assert modelo.render(Context({"valor": Decimal("1234.5")})) == "R$ 1,234.50"
    assert modelo.render(Context({"valor": None})) == ""


# --- Entries and payments --------------------------------------------------------------


def test_recepcao_lanca_parcelado(cenario):
    cliente = entrar(cenario, "recepcao")
    resposta = cliente.post(reverse("finance:entry_new"), novo(cenario))
    assert resposta.status_code == 302
    with usar_clinica(cenario["clinic"]):
        lancamento = Entry.objects.get()
        parcelas = list(lancamento.parcelas.order_by("numero"))
    assert lancamento.created_by == cenario["recepcao"]
    assert [p.valor for p in parcelas] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert [p.vencimento for p in parcelas] == [
        datetime.date(2031, 1, 31),
        datetime.date(2031, 2, 28),
        datetime.date(2031, 3, 31),
    ]


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"patient": "", "pessoa": ""}, "pessoa"),
        ({"valor_total": "0"}, "valor_total"),
        ({"recebido_agora": "on"}, "forma"),
        ({"parcelas": 0}, "parcelas"),
    ],
)
def test_validacoes_do_lancamento(cenario, extra, campo):
    resposta = entrar(cenario, "recepcao").post(
        reverse("finance:entry_new"), novo(cenario, **extra)
    )
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors


def test_pagamento_na_hora_abre_o_recibo(cenario):
    cliente = entrar(cenario, "recepcao")
    resposta = cliente.post(
        reverse("finance:entry_new"),
        novo(
            cenario,
            parcelas=1,
            valor_total="150,50",
            recebido_agora="on",
            forma=Payment.Forma.PIX,
            conta=cenario["caixa"].pk,
        ),
        follow=True,
    )
    pagina = resposta.content.decode()
    assert "RECIBO" in pagina and "R$ 150,50" in pagina and "529.982.247-25" in pagina
    with usar_clinica(cenario["clinic"]):
        assert Installment.objects.abertas().count() == 0


def test_pagamento_parcial_juros_e_saldo(cenario):
    lancamento = lancamento_com(cenario)
    primeira = parcelas_de(cenario, lancamento)[0]
    cliente = entrar(cenario, "recepcao")
    url = reverse("finance:receive_installment", args=[primeira.pk])
    dados = {"data": HOJE.isoformat(), "forma": "dinheiro", "conta": cenario["caixa"].pk}
    # 60 received, 10 of them late fee: the installment goes down by 50.
    assert cliente.post(url, {**dados, "valor": "60", "juros": "10"}).status_code == 302
    primeira = parcelas_de(cenario, lancamento)[0]
    assert (primeira.pago, primeira.saldo) == (Decimal("50.00"), Decimal("50.00"))
    assert services.situacao(primeira)[0] == "parcial"
    # Paying more than what is left is refused.
    resposta = cliente.post(url, {**dados, "valor": "50,01"})
    assert "passa do que falta" in resposta.content.decode()
    cliente.post(url, {**dados, "valor": "50"})
    assert parcelas_de(cenario, lancamento)[0].saldo == 0


def test_desconto_so_para_o_administrador(cenario):
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    url = reverse("finance:receive_installment", args=[parcela.pk])
    dados = {"data": HOJE.isoformat(), "forma": "pix", "conta": cenario["caixa"].pk}

    recepcao = entrar(cenario, "recepcao")
    assert "desconto" not in recepcao.get(url).context["form"].fields
    recepcao.post(url, {**dados, "valor": "90", "desconto": "10"})  # discount ignored
    assert parcelas_de(cenario, lancamento)[0].saldo == Decimal("10.00")

    admin = entrar(cenario, "admin")
    admin.post(url, {**dados, "valor": "5", "desconto": "5"})
    assert parcelas_de(cenario, lancamento)[0].saldo == 0


def test_estorno_e_cancelamento_so_do_administrador(cenario):
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    with usar_clinica(cenario["clinic"]):
        pagamento = services.receber(
            parcela,
            user=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
        )
    recepcao = entrar(cenario, "recepcao")
    estornar = reverse("finance:reverse_payment", args=[pagamento.pk])
    cancelar = reverse("finance:cancel", args=[lancamento.pk])
    assert recepcao.post(estornar, {"motivo": "x"}).status_code == 403
    assert recepcao.post(cancelar, {"motivo": "x"}).status_code == 403

    admin = entrar(cenario, "admin")
    # With an active payment the entry cannot be cancelled.
    resposta = admin.post(cancelar, {"motivo": "Desistiu"}, follow=True)
    assert "Estorne os pagamentos" in resposta.content.decode()
    # The page names the payment with the amount in reais (review stage 5: it read "100.00").
    assert "R$ 100,00" in admin.get(estornar).content.decode()
    admin.post(estornar, {"motivo": "Pix devolvido"})
    pagamento.refresh_from_db()
    assert pagamento.estornado and pagamento.estornado_por == cenario["admin"]
    assert parcelas_de(cenario, lancamento)[0].saldo == Decimal("100.00")
    assert (
        "ESTORNADO" in admin.get(reverse("finance:receipt", args=[pagamento.pk])).content.decode()
    )

    admin.post(cancelar, {"motivo": "Desistiu do tratamento"})
    lancamento.refresh_from_db()
    assert lancamento.cancelado and lancamento.motivo_cancelamento == "Desistiu do tratamento"
    # A second click (or a stale page) changes nothing.
    with usar_clinica(cenario["clinic"]), pytest.raises(ValidationError):
        services.cancelar(lancamento, motivo="De novo", user=cenario["admin"])
    with usar_clinica(cenario["clinic"]), pytest.raises(ValidationError):
        services.estornar(pagamento, motivo="De novo", user=cenario["admin"])
    lancamento.refresh_from_db()
    pagamento.refresh_from_db()
    assert lancamento.motivo_cancelamento == "Desistiu do tratamento"
    assert pagamento.motivo_estorno == "Pix devolvido"
    with usar_clinica(cenario["clinic"]):
        assert not Installment.objects.abertas().exists()


def test_devedores_por_tempo_de_atraso(cenario):
    lancamento_com(
        cenario, valor="200.00", parcelas=2, vencimento=HOJE - datetime.timedelta(days=45)
    )
    lancamento_com(
        cenario,
        valor="70.00",
        parcelas=1,
        vencimento=HOJE - datetime.timedelta(days=100),
        patient=False,
    )
    with usar_clinica(cenario["clinic"]):
        linhas = services.devedores()
    assert [linha["nome"] for linha in linhas] == ["Maria Devedora", "João Avulso"]
    maria, joao = linhas
    # 45 days late (31-60) and the next one 15 days late (up to 30).
    assert maria["faixas"] == [Decimal("100.00"), Decimal("100.00"), 0, 0]
    assert maria["vencido"] == Decimal("200.00")
    assert joao["faixas"][3] == Decimal("70.00")
    pagina = entrar(cenario, "recepcao").get(reverse("finance:debtors")).content.decode()
    assert "Maria Devedora" in pagina and "R$ 270,00" in pagina


def test_lista_a_receber_e_filtros(cenario):
    lancamento_com(
        cenario, valor="90.00", parcelas=3, vencimento=HOJE - datetime.timedelta(days=40)
    )
    cliente = entrar(cenario, "recepcao")
    lista = reverse("finance:receivables")
    assert len(cliente.get(lista).context["pagina"]) == 3
    assert len(cliente.get(lista, {"situacao": "vencidas"}).context["pagina"]) == 2
    assert len(cliente.get(lista, {"q": "devedora"}).context["pagina"]) == 3
    assert len(cliente.get(lista, {"q": "ninguem"}).context["pagina"]) == 0


def test_ficha_mostra_o_financeiro_do_paciente(cenario):
    lancamento_com(cenario, valor="80.00", parcelas=2, vencimento=HOJE - datetime.timedelta(days=5))
    url = reverse("patients:record", args=[cenario["patient"].pk])
    resposta = entrar(cenario, "recepcao").get(url)
    financeiro = resposta.context["financeiro"]
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
        cliente.post(url, {"nome": "Ortodontia", "tipo": "receita", "ativa": "on"}).status_code
        == 302
    )
    resposta = cliente.post(url, {"nome": "Ortodontia", "tipo": "receita", "ativa": "on"})
    assert "Já existe" in resposta.content.decode()
    cliente.post(
        reverse("finance:catalog_new", args=["accounts"]),
        {"nome": "Maquininha", "tipo": "cartao", "ativa": "on"},
    )
    with usar_clinica(cenario["clinic"]):
        assert Category.objects.filter(nome="Ortodontia").exists()
        assert FinancialAccount.objects.filter(nome="Maquininha", tipo="cartao").exists()
    assert cliente.get("/finance/something-else/").status_code == 404


def test_lancamento_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    lancamento = lancamento_com(cenario)
    outro = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert outro.get(reverse("finance:entry", args=[lancamento.pk])).status_code == 404
    assert outro.get(reverse("finance:receivables")).context["pagina"].paginator.count == 0


def test_exclusao_definitiva_mantem_o_lancamento_sem_o_paciente(cenario):
    lancamento = lancamento_com(cenario)
    with usar_clinica(cenario["clinic"]):
        Entry.objects.filter(pk=lancamento.pk).update(observacoes="Mãe: Joana, 9999-0000")
        pagamento = services.receber(
            lancamento.parcelas.first(),
            user=cenario["admin"],
            valor=Decimal("10.00"),
            forma="pix",
            conta=FinancialAccount.objects.get(nome="Caixa"),
            observacao="Pago pela Joana",
        )
        Patient.objects.filter(pk=cenario["patient"].pk).update(arquivado=True)
    admin = entrar(cenario, "admin")
    admin.post(reverse("patients:delete", args=[cenario["patient"].pk]))
    lancamento.refresh_from_db()
    pagamento.refresh_from_db()
    assert lancamento.patient is None
    assert lancamento.pessoa == f"Paciente excluído (código {cenario['patient'].pk})"
    # Notes may hold personal data; amounts stay.
    assert (lancamento.observacoes, pagamento.observacao) == ("", "")
    assert pagamento.valor == Decimal("10.00")


# --- Payables, cash flow and reports (0.16.0) ---------------------------------------------


def despesa(cenario, **extra):
    with usar_clinica(cenario["clinic"]):
        aluguel = Category.objects.get(nome="Aluguel")
    return {
        "pessoa": "Imobiliária",
        "descricao": "Aluguel",
        "categoria": aluguel.pk,
        "valor": "3.000,00".replace(".", ""),
        "modo": "repetir",
        "parcelas": 12,
        "primeiro_vencimento": "2031-01-10",
        "observacoes": "",
        **extra,
    }


def test_despesa_fixa_mensal_e_parcelada(cenario):
    admin = entrar(cenario, "admin")
    assert admin.post(reverse("finance:expense_new"), despesa(cenario)).status_code == 302
    admin.post(
        reverse("finance:expense_new"),
        despesa(cenario, descricao="Cadeira", modo="dividir", valor="900", parcelas=3),
    )
    with usar_clinica(cenario["clinic"]):
        aluguel = Entry.objects.get(descricao="Aluguel")
        cadeira = Entry.objects.get(descricao="Cadeira")
        assert aluguel.tipo == Entry.Tipo.PAGAR
        assert aluguel.valor_total == Decimal("36000.00")
        assert {p.valor for p in aluguel.parcelas.all()} == {Decimal("3000.00")}
        assert aluguel.parcelas.count() == 12
        assert [p.valor for p in cadeira.parcelas.order_by("numero")] == [Decimal("300.00")] * 3


def test_despesa_paga_na_hora_e_pagamento_de_parcela(cenario):
    admin = entrar(cenario, "admin")
    admin.post(
        reverse("finance:expense_new"),
        despesa(cenario, parcelas=2, pago_agora="on", forma="pix", conta=cenario["caixa"].pk),
    )
    with usar_clinica(cenario["clinic"]):
        lancamento = Entry.objects.get()
    segunda = parcelas_de(cenario, lancamento)[1]
    resposta = admin.post(
        reverse("finance:receive_installment", args=[segunda.pk]),
        {
            "data": HOJE.isoformat(),
            "valor": "3000",
            "forma": "boleto",
            "conta": cenario["caixa"].pk,
        },
    )
    # Paying a bill goes back to the entry (receipts are only for money received).
    assert resposta.url == reverse("finance:entry", args=[lancamento.pk])
    assert all(p.saldo == 0 for p in parcelas_de(cenario, lancamento))


def test_recepcao_nao_ve_contas_a_pagar(cenario):
    admin = entrar(cenario, "admin")
    admin.post(reverse("finance:expense_new"), despesa(cenario, parcelas=1))
    with usar_clinica(cenario["clinic"]):
        lancamento = Entry.objects.get()
        parcela = lancamento.parcelas.get()
    recepcao = entrar(cenario, "recepcao")
    for url in (
        reverse("finance:payables"),
        reverse("finance:expense_new"),
        reverse("finance:cash_flow"),
        reverse("finance:reports"),
        reverse("finance:entry", args=[lancamento.pk]),
        reverse("finance:receive_installment", args=[parcela.pk]),
    ):
        assert recepcao.get(url).status_code == 403, url
    assert reverse("finance:payables") not in recepcao.get(reverse("home")).content.decode()


def test_saldo_das_contas_com_saldo_inicial(cenario):
    with usar_clinica(cenario["clinic"]):
        FinancialAccount.objects.filter(pk=cenario["caixa"].pk).update(
            saldo_inicial=Decimal("-50.00")
        )
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    with usar_clinica(cenario["clinic"]):
        services.receber(
            parcelas_de(cenario, lancamento)[0],
            user=cenario["admin"],
            valor=Decimal("100"),
            forma="dinheiro",
            conta=cenario["caixa"],
        )
        saldos = dict((conta.nome, saldo) for conta, saldo in services.saldos_das_contas())
    assert saldos == {"Caixa": Decimal("50.00"), "Banco": Decimal("0.00")}
    # A negative initial balance is accepted in the form (overdrawn bank).
    admin = entrar(cenario, "admin")
    resposta = admin.post(
        reverse("finance:catalog_edit", args=["accounts", cenario["caixa"].pk]),
        {"nome": "Caixa", "tipo": "dinheiro", "saldo_inicial": "-10,50", "ativa": "on"},
    )
    assert resposta.status_code == 302


def test_fluxo_de_caixa_realizado_e_previsto(cenario):
    de = datetime.date(2031, 3, 1)
    ate = datetime.date(2031, 3, 31)
    recebivel = lancamento_com(
        cenario, valor="200.00", parcelas=2, vencimento=datetime.date(2031, 3, 5)
    )
    with usar_clinica(cenario["clinic"]):
        FinancialAccount.objects.filter(pk=cenario["caixa"].pk).update(
            saldo_inicial=Decimal("1000.00")
        )
        services.receber(
            parcelas_de(cenario, recebivel)[0],
            user=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
            data=datetime.date(2031, 3, 5),
        )
        aluguel = services.criar_lancamento(
            clinic=cenario["clinic"],
            tipo=Entry.Tipo.PAGAR,
            pessoa="Imobiliária",
            descricao="Aluguel",
            categoria=Category.objects.get(nome="Aluguel"),
            valor_total=Decimal("300.00"),
            parcelas=1,
            primeiro_vencimento=datetime.date(2031, 3, 10),
            user=cenario["admin"],
        )
        fluxo = services.fluxo_de_caixa(de, ate, hoje=datetime.date(2031, 3, 1))
    assert fluxo["saldo_inicial"] == Decimal("1000.00")
    linhas = {linha["data"]: linha for linha in fluxo["linhas"]}
    assert linhas[datetime.date(2031, 3, 5)]["entradas"] == Decimal("100.00")
    assert linhas[datetime.date(2031, 3, 10)]["saidas_previstas"] == Decimal("300.00")
    # 2nd receivable installment due 2031-04-05: outside the period.
    assert fluxo["saldo_final"] == Decimal("800.00")
    assert aluguel.valor_total == Decimal("300.00")
    resposta = entrar(cenario, "admin").get(
        reverse("finance:cash_flow"), {"de": "2031-03-01", "ate": "2031-03-31", "agrupar": "mes"}
    )
    assert resposta.status_code == 200 and resposta.context["por_mes"]


def test_relatorio_por_forma_categoria_e_profissional(cenario):
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    with usar_clinica(cenario["clinic"]):
        pagamento = services.receber(
            parcelas_de(cenario, lancamento)[0],
            user=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
        )
        relatorio = services.relatorio(HOJE, HOJE)
    assert relatorio["por_forma"] == [("Pix", Decimal("100.00"))]
    assert relatorio["por_categoria"] == [("Tratamento", Decimal("100.00"))]
    assert relatorio["resultado"] == Decimal("100.00")
    # Reversed payments leave the reports.
    with usar_clinica(cenario["clinic"]):
        services.estornar(pagamento, motivo="erro", user=cenario["admin"])
        assert services.relatorio(HOJE, HOJE)["total_recebido"] == 0
    assert (
        entrar(cenario, "admin").get(reverse("finance:reports"), {"de": "lixo"}).status_code == 200
    )


def test_listas_de_escolha_sem_texto_em_ingles(cenario):
    pagina = entrar(cenario, "admin").get(reverse("finance:expense_new")).content.decode()
    assert "Select an option" not in pagina


# --- Daily cash drawer (0.17.0) -----------------------------------------------------------


def test_caixa_do_dia_completo(cenario):
    from apps.finance.models import CashMovement, CashRegister

    with usar_clinica(cenario["clinic"]):
        banco = FinancialAccount.objects.get(nome="Banco")
    recepcao = entrar(cenario, "recepcao")
    assert recepcao.get(reverse("finance:cash")).status_code == 200
    resposta = recepcao.post(reverse("finance:cash"), {"valor": "100,00"})
    with usar_clinica(cenario["clinic"]):
        caixa = CashRegister.objects.get()
    assert resposta.url == reverse("finance:cash_detail", args=[caixa.pk])
    # Only one open drawer per account: the page goes straight to it.
    assert recepcao.get(reverse("finance:cash")).url == resposta.url

    # A cash payment while the drawer is open enters it; a Pix into the bank does not.
    lancamento = lancamento_com(cenario, valor="80.00", parcelas=2)
    primeira, segunda = parcelas_de(cenario, lancamento)
    with usar_clinica(cenario["clinic"]):
        services.receber(
            primeira,
            user=cenario["recepcao"],
            valor=Decimal("40"),
            forma="dinheiro",
            conta=cenario["caixa"],
        )
        services.receber(
            segunda, user=cenario["recepcao"], valor=Decimal("40"), forma="pix", conta=banco
        )

    url = lambda nome, *args: reverse(f"finance:{nome}", args=[caixa.pk, *args])  # noqa: E731
    recepcao.post(url("cash_movement", "top-up"), {"valor": "10", "motivo": "Troco"})
    recepcao.post(
        url("cash_movement", "withdrawal"),
        {"valor": "120", "motivo": "Depósito", "outra_conta": banco.pk},
    )
    # A withdrawal larger than what should be in the drawer is refused.
    resposta = recepcao.post(url("cash_movement", "withdrawal"), {"valor": "999", "motivo": "x"})
    assert "passa do valor" in resposta.content.decode()

    with usar_clinica(cenario["clinic"]):
        resumo = services.resumo_do_caixa(caixa)
        saldos = dict((c.nome, s) for c, s in services.saldos_das_contas())
    assert (resumo["entradas"], resumo["reforcos"], resumo["retiradas"]) == (
        Decimal("40.00"),
        Decimal("10.00"),
        Decimal("120.00"),
    )
    assert resumo["esperado"] == Decimal("30.00")  # 100 + 40 + 10 - 120
    # The deposit moved money from the drawer account to the bank.
    assert saldos == {"Caixa": Decimal("-70.00"), "Banco": Decimal("160.00")}

    recepcao.post(url("cash_close"), {"valor_contado": "28,50", "observacao": "Faltou troco"})
    caixa.refresh_from_db()
    assert not caixa.aberto and caixa.fechado_por == cenario["recepcao"]
    assert (caixa.valor_esperado, caixa.valor_contado, caixa.diferenca) == (
        Decimal("30.00"),
        Decimal("28.50"),
        Decimal("-1.50"),
    )
    # Closed: no more movements, and a new drawer can be opened.
    assert recepcao.get(url("cash_close")).status_code == 404
    assert recepcao.get(url("cash_movement", "other")).status_code == 404
    recepcao.post(reverse("finance:cash"), {"valor": "28,50"})
    with usar_clinica(cenario["clinic"]):
        assert CashRegister.objects.filter(fechado_em__isnull=True).count() == 1
        assert CashMovement.objects.count() == 2


def test_profissional_nao_opera_o_caixa(cenario):
    assert entrar(cenario, "practitioner").get(reverse("finance:cash")).status_code == 403


def test_caixa_fechado_nao_muda_com_estorno_posterior(cenario):
    with usar_clinica(cenario["clinic"]):
        caixa = services.abrir_caixa(cenario["caixa"], valor=Decimal("0"), user=cenario["admin"])
    lancamento = lancamento_com(cenario, valor="50.00", parcelas=1)
    with usar_clinica(cenario["clinic"]):
        pagamento = services.receber(
            parcelas_de(cenario, lancamento)[0],
            user=cenario["admin"],
            valor=Decimal("50"),
            forma="dinheiro",
            conta=cenario["caixa"],
        )
        services.fechar_caixa(
            caixa, valor_contado=Decimal("50"), observacao="", user=cenario["admin"]
        )
        services.estornar(pagamento, motivo="erro", user=cenario["admin"])
        caixa.refresh_from_db()
    assert (caixa.valor_esperado, caixa.diferenca) == (Decimal("50.00"), 0)


@pytest.mark.parametrize("digitado", ["1.500,00", "R$ 1.500,00", "1500,00", "1.500"])
def test_valor_com_ponto_de_milhar(cenario, digitado):
    """Review stage 3: "1.500,00", as people write it, was refused ("Informe um número")."""
    resposta = entrar(cenario, "admin").post(
        reverse("finance:entry_new"), novo(cenario, valor_total=digitado, parcelas=1)
    )
    assert resposta.status_code == 302, resposta.context["form"].errors
    with usar_clinica(cenario["clinic"]):
        assert Entry.objects.get().valor_total == Decimal("1500.00")


def test_cheque_nao_e_mais_oferecido(cenario):
    """The owner: cheques are not used anymore. A cheque recorded before keeps its name."""
    lancamento = lancamento_com(cenario)
    parcela = parcelas_de(cenario, lancamento)[0]
    admin = entrar(cenario, "admin")
    for url in (
        reverse("finance:receive_installment", args=[parcela.pk]),
        reverse("finance:entry_new"),
        reverse("finance:expense_new"),
    ):
        pagina = admin.get(url).content.decode()
        assert 'value="pix"' in pagina and 'value="cheque"' not in pagina, url
    recusado = admin.post(
        reverse("finance:receive_installment", args=[parcela.pk]),
        {"data": "2026-10-30", "valor": "100,00", "forma": "cheque", "conta": cenario["caixa"].pk},
    )
    assert "forma" in recusado.context["form"].errors
    with usar_clinica(cenario["clinic"]):
        antigo = services.receber(
            parcela,
            user=cenario["admin"],
            valor=Decimal("100"),
            forma="cheque",
            conta=cenario["caixa"],
        )
    assert antigo.get_forma_display() == "Cheque"


def test_devedores_paginados_e_com_busca(cenario):
    """Volume test: thousands of debtors filled a single page of several MB."""
    with usar_clinica(cenario["clinic"]):
        for n in range(55):
            services.criar_lancamento(
                clinic=cenario["clinic"],
                tipo=Entry.Tipo.RECEBER,
                pessoa=f"Pagador Fictício {n:02d}",
                descricao="Consulta",
                categoria=cenario["categoria"],
                valor_total=Decimal("10"),
                parcelas=1,
                primeiro_vencimento=HOJE - datetime.timedelta(days=10),
                user=cenario["admin"],
            )
    cliente = entrar(cenario, "recepcao")
    primeira = cliente.get(reverse("finance:debtors")).content.decode()
    assert "55 devedores" in primeira and "Página 1 de 2" in primeira
    assert "R$ 550,00" in primeira  # the totals still add up everyone
    busca = cliente.get(reverse("finance:debtors"), {"q": "fictício 07"}).content.decode()
    assert "Pagador Fictício 07" in busca and "Pagador Fictício 08" not in busca
