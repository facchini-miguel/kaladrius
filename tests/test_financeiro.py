"""Receivables (0.15.0): installments, payments, receipts, debtors and permissions."""

import datetime
from decimal import Decimal

import pytest
from django.template import Context, Template
from django.urls import reverse
from django.utils import timezone, translation

from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica, Papel
from apps.financeiro import servicos
from apps.financeiro.models import Categoria, Conta, Lancamento, Pagamento, Parcela
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Maria Devedora", cpf_cnpj="52998224725")
        categoria = Categoria.objects.get(nome="Tratamento")
        caixa = Conta.objects.get(nome="Caixa")
    return {
        "clinica": clinica_a,
        "paciente": paciente,
        "categoria": categoria,
        "caixa": caixa,
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "profissional": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def novo(cenario, **extra):
    return {
        "paciente": cenario["paciente"].pk,
        "pessoa": "",
        "descricao": "Tratamento de canal",
        "categoria": cenario["categoria"].pk,
        "profissional": "",
        "valor_total": "100,00",
        "parcelas": 3,
        "primeiro_vencimento": "2031-01-31",
        "observacoes": "",
        **extra,
    }


def lancamento_com(cenario, valor="300.00", parcelas=3, vencimento=None, paciente=True):
    with usar_clinica(cenario["clinica"]):
        return servicos.criar_lancamento(
            clinica=cenario["clinica"],
            tipo=Lancamento.Tipo.RECEBER,
            paciente=cenario["paciente"] if paciente else None,
            pessoa="" if paciente else "João Avulso",
            descricao="Prótese",
            categoria=cenario["categoria"],
            valor_total=Decimal(valor),
            parcelas=parcelas,
            primeiro_vencimento=vencimento or HOJE,
            usuario=cenario["admin"],
        )


def parcelas_de(cenario, lancamento):
    with usar_clinica(cenario["clinica"]):
        return list(Parcela.objects.com_saldo().filter(lancamento=lancamento).order_by("numero"))


# --- Rules -----------------------------------------------------------------------------


def test_divisao_em_parcelas_e_vencimentos_mensais():
    assert servicos.dividir(Decimal("100.00"), 3) == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert servicos.somar_meses(datetime.date(2031, 1, 31), 1) == datetime.date(2031, 2, 28)
    assert servicos.somar_meses(datetime.date(2031, 11, 15), 3) == datetime.date(2032, 2, 15)


def test_clinica_nova_recebe_contas_e_categorias_padrao():
    clinica = Clinica.objects.create(nome="Clínica Nova")
    with usar_clinica(clinica):
        assert set(Conta.objects.values_list("nome", flat=True)) == {"Caixa", "Banco"}
        assert Categoria.objects.filter(tipo=Categoria.Tipo.RECEITA).count() == 3
        assert Categoria.objects.filter(tipo=Categoria.Tipo.DESPESA).count() == 8


def test_moeda_no_formato_do_idioma():
    modelo = Template("{% load formatos %}{{ valor|moeda }}")
    with translation.override("pt-br"):
        assert modelo.render(Context({"valor": Decimal("1234.5")})) == "R$ 1.234,50"
    with translation.override("en"):
        assert modelo.render(Context({"valor": Decimal("1234.5")})) == "R$ 1,234.50"
    assert modelo.render(Context({"valor": None})) == ""


# --- Entries and payments --------------------------------------------------------------


def test_recepcao_lanca_parcelado(cenario):
    cliente = entrar(cenario, "recepcao")
    resposta = cliente.post(reverse("financeiro:lancamento_novo"), novo(cenario))
    assert resposta.status_code == 302
    with usar_clinica(cenario["clinica"]):
        lancamento = Lancamento.objects.get()
        parcelas = list(lancamento.parcelas.order_by("numero"))
    assert lancamento.criado_por == cenario["recepcao"]
    assert [p.valor for p in parcelas] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert [p.vencimento for p in parcelas] == [
        datetime.date(2031, 1, 31),
        datetime.date(2031, 2, 28),
        datetime.date(2031, 3, 31),
    ]


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"paciente": "", "pessoa": ""}, "pessoa"),
        ({"valor_total": "0"}, "valor_total"),
        ({"recebido_agora": "on"}, "forma"),
        ({"parcelas": 0}, "parcelas"),
    ],
)
def test_validacoes_do_lancamento(cenario, extra, campo):
    resposta = entrar(cenario, "recepcao").post(
        reverse("financeiro:lancamento_novo"), novo(cenario, **extra)
    )
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors


def test_pagamento_na_hora_abre_o_recibo(cenario):
    cliente = entrar(cenario, "recepcao")
    resposta = cliente.post(
        reverse("financeiro:lancamento_novo"),
        novo(
            cenario,
            parcelas=1,
            valor_total="150,50",
            recebido_agora="on",
            forma=Pagamento.Forma.PIX,
            conta=cenario["caixa"].pk,
        ),
        follow=True,
    )
    pagina = resposta.content.decode()
    assert "RECIBO" in pagina and "R$ 150,50" in pagina and "529.982.247-25" in pagina
    with usar_clinica(cenario["clinica"]):
        assert Parcela.objects.abertas().count() == 0


def test_pagamento_parcial_juros_e_saldo(cenario):
    lancamento = lancamento_com(cenario)
    primeira = parcelas_de(cenario, lancamento)[0]
    cliente = entrar(cenario, "recepcao")
    url = reverse("financeiro:receber_parcela", args=[primeira.pk])
    dados = {"data": HOJE.isoformat(), "forma": "dinheiro", "conta": cenario["caixa"].pk}
    # 60 received, 10 of them late fee: the installment goes down by 50.
    assert cliente.post(url, {**dados, "valor": "60", "juros": "10"}).status_code == 302
    primeira = parcelas_de(cenario, lancamento)[0]
    assert (primeira.pago, primeira.saldo) == (Decimal("50.00"), Decimal("50.00"))
    assert servicos.situacao(primeira)[0] == "parcial"
    # Paying more than what is left is refused.
    resposta = cliente.post(url, {**dados, "valor": "50,01"})
    assert "passa do que falta" in resposta.content.decode()
    cliente.post(url, {**dados, "valor": "50"})
    assert parcelas_de(cenario, lancamento)[0].saldo == 0


def test_desconto_so_para_o_administrador(cenario):
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    parcela = parcelas_de(cenario, lancamento)[0]
    url = reverse("financeiro:receber_parcela", args=[parcela.pk])
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
    with usar_clinica(cenario["clinica"]):
        pagamento = servicos.receber(
            parcela,
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
        )
    recepcao = entrar(cenario, "recepcao")
    estornar = reverse("financeiro:estornar", args=[pagamento.pk])
    cancelar = reverse("financeiro:cancelar", args=[lancamento.pk])
    assert recepcao.post(estornar, {"motivo": "x"}).status_code == 403
    assert recepcao.post(cancelar, {"motivo": "x"}).status_code == 403

    admin = entrar(cenario, "admin")
    # With an active payment the entry cannot be cancelled.
    resposta = admin.post(cancelar, {"motivo": "Desistiu"}, follow=True)
    assert "Estorne os pagamentos" in resposta.content.decode()
    admin.post(estornar, {"motivo": "Pix devolvido"})
    pagamento.refresh_from_db()
    assert pagamento.estornado and pagamento.estornado_por == cenario["admin"]
    assert parcelas_de(cenario, lancamento)[0].saldo == Decimal("100.00")
    assert (
        "ESTORNADO" in admin.get(reverse("financeiro:recibo", args=[pagamento.pk])).content.decode()
    )

    admin.post(cancelar, {"motivo": "Desistiu do tratamento"})
    lancamento.refresh_from_db()
    assert lancamento.cancelado and lancamento.motivo_cancelamento == "Desistiu do tratamento"
    with usar_clinica(cenario["clinica"]):
        assert not Parcela.objects.abertas().exists()


def test_devedores_por_tempo_de_atraso(cenario):
    lancamento_com(
        cenario, valor="200.00", parcelas=2, vencimento=HOJE - datetime.timedelta(days=45)
    )
    lancamento_com(
        cenario,
        valor="70.00",
        parcelas=1,
        vencimento=HOJE - datetime.timedelta(days=100),
        paciente=False,
    )
    with usar_clinica(cenario["clinica"]):
        linhas = servicos.devedores()
    assert [linha["nome"] for linha in linhas] == ["Maria Devedora", "João Avulso"]
    maria, joao = linhas
    # 45 days late (31-60) and the next one 15 days late (up to 30).
    assert maria["faixas"] == [Decimal("100.00"), Decimal("100.00"), 0, 0]
    assert maria["vencido"] == Decimal("200.00")
    assert joao["faixas"][3] == Decimal("70.00")
    pagina = entrar(cenario, "recepcao").get(reverse("financeiro:devedores")).content.decode()
    assert "Maria Devedora" in pagina and "R$ 270,00" in pagina


def test_lista_a_receber_e_filtros(cenario):
    lancamento_com(
        cenario, valor="90.00", parcelas=3, vencimento=HOJE - datetime.timedelta(days=40)
    )
    cliente = entrar(cenario, "recepcao")
    lista = reverse("financeiro:receber")
    assert len(cliente.get(lista).context["pagina"]) == 3
    assert len(cliente.get(lista, {"situacao": "vencidas"}).context["pagina"]) == 2
    assert len(cliente.get(lista, {"q": "devedora"}).context["pagina"]) == 3
    assert len(cliente.get(lista, {"q": "ninguem"}).context["pagina"]) == 0


def test_ficha_mostra_o_financeiro_do_paciente(cenario):
    lancamento_com(cenario, valor="80.00", parcelas=2, vencimento=HOJE - datetime.timedelta(days=5))
    url = reverse("pacientes:ficha", args=[cenario["paciente"].pk])
    resposta = entrar(cenario, "recepcao").get(url)
    financeiro = resposta.context["financeiro"]
    assert (financeiro["vencido"], financeiro["a_vencer"]) == (Decimal("40.00"), Decimal("40.00"))
    # Practitioners do not see the finances.
    assert "financeiro" not in entrar(cenario, "profissional").get(url).context


# --- Permissions, isolation, records -----------------------------------------------------


def test_profissional_nao_acessa_o_financeiro(cenario):
    cliente = entrar(cenario, "profissional")
    assert cliente.get(reverse("financeiro:receber")).status_code == 403
    assert cliente.get(reverse("financeiro:devedores")).status_code == 403
    assert reverse("financeiro:receber") not in cliente.get(reverse("inicio")).content.decode()


def test_recepcao_nao_mexe_em_categorias_e_contas(cenario):
    cliente = entrar(cenario, "recepcao")
    assert cliente.get(reverse("financeiro:cadastro", args=["categorias"])).status_code == 403
    assert cliente.get(reverse("financeiro:cadastro_novo", args=["contas"])).status_code == 403


def test_admin_cadastra_categorias_e_contas(cenario):
    cliente = entrar(cenario, "admin")
    url = reverse("financeiro:cadastro_novo", args=["categorias"])
    assert (
        cliente.post(url, {"nome": "Ortodontia", "tipo": "receita", "ativa": "on"}).status_code
        == 302
    )
    resposta = cliente.post(url, {"nome": "Ortodontia", "tipo": "receita", "ativa": "on"})
    assert "Já existe" in resposta.content.decode()
    cliente.post(
        reverse("financeiro:cadastro_novo", args=["contas"]),
        {"nome": "Maquininha", "tipo": "cartao", "ativa": "on"},
    )
    with usar_clinica(cenario["clinica"]):
        assert Categoria.objects.filter(nome="Ortodontia").exists()
        assert Conta.objects.filter(nome="Maquininha", tipo="cartao").exists()
    assert cliente.get("/financeiro/outra-coisa/").status_code == 404


def test_lancamento_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    lancamento = lancamento_com(cenario)
    outro = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert outro.get(reverse("financeiro:lancamento", args=[lancamento.pk])).status_code == 404
    assert outro.get(reverse("financeiro:receber")).context["pagina"].paginator.count == 0


def test_exclusao_definitiva_mantem_o_lancamento_sem_o_paciente(cenario):
    lancamento = lancamento_com(cenario)
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.filter(pk=cenario["paciente"].pk).update(arquivado=True)
    admin = entrar(cenario, "admin")
    admin.post(reverse("pacientes:excluir", args=[cenario["paciente"].pk]))
    lancamento.refresh_from_db()
    assert lancamento.paciente is None
    assert lancamento.pessoa == f"Paciente excluído (código {cenario['paciente'].pk})"


# --- Payables, cash flow and reports (0.16.0) ---------------------------------------------


def despesa(cenario, **extra):
    with usar_clinica(cenario["clinica"]):
        aluguel = Categoria.objects.get(nome="Aluguel")
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
    assert admin.post(reverse("financeiro:despesa_nova"), despesa(cenario)).status_code == 302
    admin.post(
        reverse("financeiro:despesa_nova"),
        despesa(cenario, descricao="Cadeira", modo="dividir", valor="900", parcelas=3),
    )
    with usar_clinica(cenario["clinica"]):
        aluguel = Lancamento.objects.get(descricao="Aluguel")
        cadeira = Lancamento.objects.get(descricao="Cadeira")
        assert aluguel.tipo == Lancamento.Tipo.PAGAR
        assert aluguel.valor_total == Decimal("36000.00")
        assert {p.valor for p in aluguel.parcelas.all()} == {Decimal("3000.00")}
        assert aluguel.parcelas.count() == 12
        assert [p.valor for p in cadeira.parcelas.order_by("numero")] == [Decimal("300.00")] * 3


def test_despesa_paga_na_hora_e_pagamento_de_parcela(cenario):
    admin = entrar(cenario, "admin")
    admin.post(
        reverse("financeiro:despesa_nova"),
        despesa(cenario, parcelas=2, pago_agora="on", forma="pix", conta=cenario["caixa"].pk),
    )
    with usar_clinica(cenario["clinica"]):
        lancamento = Lancamento.objects.get()
    segunda = parcelas_de(cenario, lancamento)[1]
    resposta = admin.post(
        reverse("financeiro:receber_parcela", args=[segunda.pk]),
        {
            "data": HOJE.isoformat(),
            "valor": "3000",
            "forma": "boleto",
            "conta": cenario["caixa"].pk,
        },
    )
    # Paying a bill goes back to the entry (receipts are only for money received).
    assert resposta.url == reverse("financeiro:lancamento", args=[lancamento.pk])
    assert all(p.saldo == 0 for p in parcelas_de(cenario, lancamento))


def test_recepcao_nao_ve_contas_a_pagar(cenario):
    admin = entrar(cenario, "admin")
    admin.post(reverse("financeiro:despesa_nova"), despesa(cenario, parcelas=1))
    with usar_clinica(cenario["clinica"]):
        lancamento = Lancamento.objects.get()
        parcela = lancamento.parcelas.get()
    recepcao = entrar(cenario, "recepcao")
    for url in (
        reverse("financeiro:pagar"),
        reverse("financeiro:despesa_nova"),
        reverse("financeiro:fluxo"),
        reverse("financeiro:relatorios"),
        reverse("financeiro:lancamento", args=[lancamento.pk]),
        reverse("financeiro:receber_parcela", args=[parcela.pk]),
    ):
        assert recepcao.get(url).status_code == 403, url
    assert reverse("financeiro:pagar") not in recepcao.get(reverse("inicio")).content.decode()


def test_saldo_das_contas_com_saldo_inicial(cenario):
    with usar_clinica(cenario["clinica"]):
        Conta.objects.filter(pk=cenario["caixa"].pk).update(saldo_inicial=Decimal("-50.00"))
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    with usar_clinica(cenario["clinica"]):
        servicos.receber(
            parcelas_de(cenario, lancamento)[0],
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="dinheiro",
            conta=cenario["caixa"],
        )
        saldos = dict((conta.nome, saldo) for conta, saldo in servicos.saldos_das_contas())
    assert saldos == {"Caixa": Decimal("50.00"), "Banco": Decimal("0.00")}
    # A negative initial balance is accepted in the form (overdrawn bank).
    admin = entrar(cenario, "admin")
    resposta = admin.post(
        reverse("financeiro:cadastro_editar", args=["contas", cenario["caixa"].pk]),
        {"nome": "Caixa", "tipo": "dinheiro", "saldo_inicial": "-10,50", "ativa": "on"},
    )
    assert resposta.status_code == 302


def test_fluxo_de_caixa_realizado_e_previsto(cenario):
    de = datetime.date(2031, 3, 1)
    ate = datetime.date(2031, 3, 31)
    recebivel = lancamento_com(
        cenario, valor="200.00", parcelas=2, vencimento=datetime.date(2031, 3, 5)
    )
    with usar_clinica(cenario["clinica"]):
        Conta.objects.filter(pk=cenario["caixa"].pk).update(saldo_inicial=Decimal("1000.00"))
        servicos.receber(
            parcelas_de(cenario, recebivel)[0],
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
            data=datetime.date(2031, 3, 5),
        )
        aluguel = servicos.criar_lancamento(
            clinica=cenario["clinica"],
            tipo=Lancamento.Tipo.PAGAR,
            pessoa="Imobiliária",
            descricao="Aluguel",
            categoria=Categoria.objects.get(nome="Aluguel"),
            valor_total=Decimal("300.00"),
            parcelas=1,
            primeiro_vencimento=datetime.date(2031, 3, 10),
            usuario=cenario["admin"],
        )
        fluxo = servicos.fluxo_de_caixa(de, ate, hoje=datetime.date(2031, 3, 1))
    assert fluxo["saldo_inicial"] == Decimal("1000.00")
    linhas = {linha["data"]: linha for linha in fluxo["linhas"]}
    assert linhas[datetime.date(2031, 3, 5)]["entradas"] == Decimal("100.00")
    assert linhas[datetime.date(2031, 3, 10)]["saidas_previstas"] == Decimal("300.00")
    # 2nd receivable installment due 2031-04-05: outside the period.
    assert fluxo["saldo_final"] == Decimal("800.00")
    assert aluguel.valor_total == Decimal("300.00")
    resposta = entrar(cenario, "admin").get(
        reverse("financeiro:fluxo"), {"de": "2031-03-01", "ate": "2031-03-31", "agrupar": "mes"}
    )
    assert resposta.status_code == 200 and resposta.context["por_mes"]


def test_relatorio_por_forma_categoria_e_profissional(cenario):
    lancamento = lancamento_com(cenario, valor="100.00", parcelas=1)
    with usar_clinica(cenario["clinica"]):
        pagamento = servicos.receber(
            parcelas_de(cenario, lancamento)[0],
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="pix",
            conta=cenario["caixa"],
        )
        relatorio = servicos.relatorio(HOJE, HOJE)
    assert relatorio["por_forma"] == [("Pix", Decimal("100.00"))]
    assert relatorio["por_categoria"] == [("Tratamento", Decimal("100.00"))]
    assert relatorio["resultado"] == Decimal("100.00")
    # Reversed payments leave the reports.
    with usar_clinica(cenario["clinica"]):
        servicos.estornar(pagamento, motivo="erro", usuario=cenario["admin"])
        assert servicos.relatorio(HOJE, HOJE)["total_recebido"] == 0
    assert (
        entrar(cenario, "admin").get(reverse("financeiro:relatorios"), {"de": "lixo"}).status_code
        == 200
    )


def test_listas_de_escolha_sem_texto_em_ingles(cenario):
    pagina = entrar(cenario, "admin").get(reverse("financeiro:despesa_nova")).content.decode()
    assert "Select an option" not in pagina
