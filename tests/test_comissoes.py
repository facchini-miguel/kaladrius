"""Practitioner commission (0.19.0): percentage of what is received, paid once."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import comissoes, servicos
from apps.financeiro.models import Categoria, Comissao, Conta, Lancamento, Pagamento
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db
HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    admin = criar_usuario("admin", clinica_a, Papel.ADMIN)
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Paulo Paciente")
        dra = Profissional.objects.create(nome="Dra. Ana", comissao_percentual=Decimal("40"))
        dr = Profissional.objects.create(nome="Dr. Beto")
        tratamento = Categoria.objects.get(nome="Tratamento")
        caixa = Conta.objects.get(nome="Caixa")
        categoria = Categoria.objects.get(nome="Comissões")
    return {
        "clinica": clinica_a,
        "paciente": paciente,
        "dra": dra,
        "dr": dr,
        "tratamento": tratamento,
        "caixa": caixa,
        "categoria": categoria,
        "admin": admin,
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        # The test client is shared: log in as the administrator by default.
        "cliente": cliente_de(admin),
        "cliente_de": cliente_de,
    }


def receber(cenario, valor, profissional, data=ONTEM, juros="0"):
    """A receivable for `valor` paid in full on `data`."""
    with usar_clinica(cenario["clinica"]):
        lancamento = servicos.criar_lancamento(
            clinica=cenario["clinica"],
            tipo=Lancamento.Tipo.RECEBER,
            paciente=cenario["paciente"],
            profissional=profissional,
            descricao="Tratamento",
            categoria=cenario["tratamento"],
            valor_total=Decimal(valor),
            parcelas=1,
            primeiro_vencimento=data,
            usuario=cenario["admin"],
        )
        return servicos.receber(
            lancamento.parcelas.get(),
            usuario=cenario["admin"],
            valor=Decimal(valor) + Decimal(juros),
            juros=Decimal(juros),
            forma="pix",
            conta=cenario["caixa"],
            data=data,
        )


def pagar_comissao(cenario, profissional, ate=HOJE):
    return cenario["cliente"].post(
        f"{reverse('financeiro:comissao_pagar', args=[profissional.pk])}?ate={ate.isoformat()}",
        {"vencimento": HOJE.isoformat(), "categoria": cenario["categoria"].pk},
    )


def test_calculo_inclui_juros_e_ignora_outros_profissionais(cenario):
    receber(cenario, "100.00", cenario["dra"], juros="10.00")
    receber(cenario, "250.55", cenario["dra"])
    receber(cenario, "999.00", cenario["dr"])  # other practitioner
    receber(cenario, "500.00", None)  # no practitioner: no commission
    receber(cenario, "80.00", cenario["dra"], data=HOJE)  # after the cut-off date
    with usar_clinica(cenario["clinica"]):
        calculo = comissoes.pendente(cenario["dra"], ONTEM)
    assert calculo["recebido"] == Decimal("360.55")
    assert calculo["valor"] == Decimal("144.22")  # 40% of 360.55, rounded half up


def test_pagar_cria_despesa_e_nao_paga_duas_vezes(cenario):
    receber(cenario, "300.00", cenario["dra"])
    resposta = pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinica"]):
        comissao = Comissao.objects.get()
        lancamento = comissao.lancamento
        assert resposta.url == reverse("financeiro:lancamento", args=[lancamento.pk])
        assert (lancamento.tipo, lancamento.valor_total, lancamento.pessoa) == (
            Lancamento.Tipo.PAGAR,
            Decimal("120.00"),
            "Dra. Ana",
        )
        assert lancamento.categoria.nome == "Comissões"
        assert Pagamento.objects.get().comissao == comissao
        assert comissoes.pendente(cenario["dra"], HOJE)["valor"] == 0
    # Paying again finds nothing.
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinica"]):
        assert Comissao.objects.count() == 1
    # Only new receipts make up the next one.
    receber(cenario, "50.00", cenario["dra"], data=HOJE)
    with usar_clinica(cenario["clinica"]):
        assert comissoes.pendente(cenario["dra"], HOJE)["valor"] == Decimal("20.00")


def test_estorno_depois_de_pago_e_descontado_no_proximo(cenario):
    pagamento = receber(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    # The percentage changes, but the deduction uses the one it was paid with (40%).
    with usar_clinica(cenario["clinica"]):
        Profissional.objects.filter(pk=cenario["dra"].pk).update(comissao_percentual=10)
        cenario["dra"].refresh_from_db()
        servicos.estornar(pagamento, motivo="Pix devolvido", usuario=cenario["admin"])
    receber(cenario, "1000.00", cenario["dra"], data=HOJE)
    with usar_clinica(cenario["clinica"]):
        calculo = comissoes.pendente(cenario["dra"], HOJE)
        assert (calculo["bruta"], calculo["estornos"], calculo["valor"]) == (
            Decimal("100.00"),
            Decimal("120.00"),
            Decimal("-20.00"),
        )
    # Nothing to pay while the deduction is larger: it waits for more receipts.
    pagar_comissao(cenario, cenario["dra"])
    receber(cenario, "500.00", cenario["dra"], data=HOJE)
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinica"]):
        segunda = Comissao.objects.latest("pk")
        assert (segunda.bruta, segunda.estornos, segunda.valor) == (
            Decimal("150.00"),
            Decimal("120.00"),
            Decimal("30.00"),
        )
        pagamento.refresh_from_db()
        assert pagamento.comissao_estorno == segunda
    extrato = cenario["cliente"].get(reverse("financeiro:comissao", args=[segunda.pk]))
    assert "Pix devolvido" not in extrato.content.decode()  # reasons are not on the statement
    assert list(extrato.context["estornos"]) == [pagamento]


def test_cancelar_a_despesa_desfaz_a_comissao(cenario):
    receber(cenario, "300.00", cenario["dra"])
    pagar_comissao(cenario, cenario["dra"])
    with usar_clinica(cenario["clinica"]):
        comissao = Comissao.objects.get()
    cenario["cliente"].post(
        reverse("financeiro:cancelar", args=[comissao.lancamento_id]), {"motivo": "Errado"}
    )
    comissao.refresh_from_db()
    assert comissao.cancelada
    with usar_clinica(cenario["clinica"]):
        assert not Pagamento.objects.filter(comissao__isnull=False).exists()
        assert comissoes.pendente(cenario["dra"], HOJE)["valor"] == Decimal("120.00")


def test_telas_e_percentual(cenario):
    receber(cenario, "300.00", cenario["dra"])
    cliente = cenario["cliente"]
    pagina = cliente.get(reverse("financeiro:comissoes"))
    assert [linha["profissional"] for linha in pagina.context["linhas"]] == [cenario["dra"]]
    assert list(pagina.context["sem_percentual"]) == [cenario["dr"]]
    assert "R$ 120,00" in pagina.content.decode()
    url = reverse("financeiro:comissao_percentual", args=[cenario["dr"].pk])
    assert cliente.post(url, {"comissao_percentual": "101"}).status_code == 200  # > 100
    cliente.post(url, {"comissao_percentual": "35,5"})
    cenario["dr"].refresh_from_db()
    assert cenario["dr"].comissao_percentual == Decimal("35.50")
    pagar = cliente.get(reverse("financeiro:comissao_pagar", args=[cenario["dra"].pk]))
    assert pagar.context["calculo"]["valor"] == Decimal("120.00")
    # A future cut-off date is not allowed: it becomes today.
    futuro = (HOJE + datetime.timedelta(days=30)).isoformat()
    assert cliente.get(reverse("financeiro:comissoes"), {"ate": futuro}).context["ate"] == HOJE


def test_so_o_administrador(cenario):
    recepcao = cenario["cliente_de"](cenario["recepcao"])
    assert recepcao.get(reverse("financeiro:comissoes")).status_code == 403
    assert (
        recepcao.post(reverse("financeiro:comissao_pagar", args=[cenario["dra"].pk])).status_code
        == 403
    )
    assert (
        recepcao.post(
            reverse("financeiro:comissao_percentual", args=[cenario["dra"].pk]),
            {"comissao_percentual": "90"},
        ).status_code
        == 403
    )


def test_profissional_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    outro = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert (
        outro.get(reverse("financeiro:comissao_pagar", args=[cenario["dra"].pk])).status_code == 404
    )
