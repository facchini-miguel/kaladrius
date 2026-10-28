"""Procedure price list and treatment estimates (0.18.0)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro.models import Categoria, Conta, Lancamento
from apps.orcamentos import servicos
from apps.orcamentos.models import ItemOrcamento, Orcamento, Procedimento
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db
HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Joana Sorriso")
        tratamento = Categoria.objects.get(nome="Tratamento")
        canal = Procedimento.objects.create(
            nome="Tratamento de canal", valor=Decimal("1200"), categoria=tratamento
        )
        restauracao = Procedimento.objects.create(nome="Restauração", valor=Decimal("250"))
    return {
        "clinica": clinica_a,
        "paciente": paciente,
        "canal": canal,
        "restauracao": restauracao,
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "profissional": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def criar_orcamento(cenario, cliente):
    resposta = cliente.post(
        reverse("orcamentos:novo"),
        {
            "paciente": cenario["paciente"].pk,
            "profissional": "",
            "data": HOJE.isoformat(),
            "validade": HOJE.isoformat(),
            "observacoes": "",
        },
    )
    with usar_clinica(cenario["clinica"]):
        orcamento = Orcamento.objects.latest("pk")
    assert resposta.url == reverse("orcamentos:detalhe", args=[orcamento.pk])
    return orcamento


def incluir(cliente, orcamento, **dados):
    return cliente.post(
        reverse("orcamentos:item_adicionar", args=[orcamento.pk]),
        {
            "descricao": "",
            "dentes": "",
            "faces": "",
            "quantidade": 1,
            "valor_unitario": "",
            **dados,
        },
    )


def test_profissional_monta_orcamento_com_dentes(cenario):
    cliente = entrar(cenario, "profissional")
    orcamento = criar_orcamento(cenario, cliente)
    # Description and price come from the price list; teeth are normalized.
    incluir(
        cliente, orcamento, procedimento=cenario["restauracao"].pk, dentes="36, 11,11", quantidade=2
    )
    incluir(cliente, orcamento, descricao="Moldagem", valor_unitario="80,00")
    with usar_clinica(cenario["clinica"]):
        itens = list(orcamento.itens.order_by("pk"))
        orcamento.refresh_from_db()
        assert orcamento.total == Decimal("580.00")
        assert orcamento.dentes == [11, 36]
    assert (itens[0].descricao, itens[0].dentes, itens[0].valor_unitario) == (
        "Restauração",
        "11,36",
        Decimal("250.00"),
    )
    assert itens[0].dentes_exibicao == "11, 36"
    pagina = cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).content.decode()
    assert 'data-dente="36"' in pagina and "R$ 580,00" in pagina


@pytest.mark.parametrize(
    "dados",
    [
        {"dentes": "19"},  # no such tooth
        {"procedimento": ""},  # neither procedure nor description
    ],
)
def test_itens_invalidos(cenario, dados):
    cliente = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, cliente)
    incluir(cliente, orcamento, **{"procedimento": cenario["canal"].pk, **dados})
    with usar_clinica(cenario["clinica"]):
        assert not orcamento.itens.exists()


def test_quem_escreve_o_orcamento_da_desconto(cenario):
    # Front desk, practitioner and administrator (0.27.1, decision 074).
    recepcao = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, recepcao)
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk)
    url = reverse("orcamentos:desconto", args=[orcamento.pk])
    assert recepcao.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).context["desconto_form"]
    recepcao.post(url, {"desconto": "5000"})  # more than the total: refused
    orcamento.refresh_from_db()
    assert orcamento.desconto == 0
    recepcao.post(url, {"desconto": "200"})
    orcamento.refresh_from_db()
    assert orcamento.desconto == Decimal("200.00")
    for quem, valor in [("profissional", "150"), ("admin", "100")]:
        entrar(cenario, quem).post(url, {"desconto": valor})
        orcamento.refresh_from_db()
        assert orcamento.desconto == Decimal(valor)


def test_aprovar_vira_lancamento_a_receber(cenario):
    recepcao = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, recepcao)
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk)
    with usar_clinica(cenario["clinica"]):
        Orcamento.objects.filter(pk=orcamento.pk).update(desconto=Decimal("200"))
        caixa = Conta.objects.get(nome="Caixa")
    url = reverse("orcamentos:aprovar", args=[orcamento.pk])
    # The category comes from the first procedure.
    assert recepcao.get(url).context["form"].initial["categoria"] == cenario["canal"].categoria
    resposta = recepcao.post(
        url,
        {
            "parcelas": 4,
            "primeiro_vencimento": HOJE.isoformat(),
            "categoria": cenario["canal"].categoria.pk,
            "recebido_agora": "on",
            "forma": "pix",
            "conta": caixa.pk,
        },
    )
    orcamento.refresh_from_db()
    lancamento = orcamento.lancamento
    assert resposta.url == reverse("financeiro:lancamento", args=[lancamento.pk])
    assert orcamento.situacao == Orcamento.Situacao.APROVADO
    assert (lancamento.tipo, lancamento.valor_total) == (
        Lancamento.Tipo.RECEBER,
        Decimal("1000.00"),
    )
    with usar_clinica(cenario["clinica"]):
        assert lancamento.parcelas.count() == 4
        assert lancamento.paciente == cenario["paciente"]
    # Once approved, nothing changes any more.
    incluir(recepcao, orcamento, procedimento=cenario["restauracao"].pk)
    with usar_clinica(cenario["clinica"]):
        assert orcamento.itens.count() == 1
    assert recepcao.post(reverse("orcamentos:recusar", args=[orcamento.pk])).status_code == 302
    orcamento.refresh_from_db()
    assert orcamento.situacao == Orcamento.Situacao.APROVADO


def test_profissional_nao_aprova(cenario):
    cliente = entrar(cenario, "profissional")
    orcamento = criar_orcamento(cenario, cliente)
    assert cliente.get(reverse("orcamentos:aprovar", args=[orcamento.pk])).status_code == 403
    assert not cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).context[
        "pode_aprovar"
    ]


def test_recusar_e_imprimir(cenario):
    cliente = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, cliente)
    incluir(cliente, orcamento, procedimento=cenario["canal"].pk, dentes="46")
    pagina = cliente.get(reverse("orcamentos:imprimir", args=[orcamento.pk])).content.decode()
    assert "ORÇAMENTO" in pagina and "Joana Sorriso" in pagina and "selecionado" in pagina
    cliente.post(reverse("orcamentos:recusar", args=[orcamento.pk]))
    orcamento.refresh_from_db()
    assert orcamento.situacao == Orcamento.Situacao.RECUSADO
    # Deciding again (e.g. a stale page approving it meanwhile) is refused.
    with usar_clinica(cenario["clinica"]), pytest.raises(ValidationError):
        servicos.recusar(orcamento, usuario=None)
    lista = cliente.get(reverse("orcamentos:lista"), {"situacao": "recusado"})
    assert list(lista.context["pagina"]) == [orcamento]


def test_ficha_mostra_orcamentos_e_arquivado_some(cenario):
    cliente = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, cliente)
    ficha = cliente.get(reverse("pacientes:ficha", args=[cenario["paciente"].pk]))
    assert ficha.context["orcamentos"] == [orcamento]
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.filter(pk=cenario["paciente"].pk).update(arquivado=True)
    assert cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).status_code == 404


def test_tabela_de_procedimentos_so_o_admin_altera(cenario):
    recepcao = entrar(cenario, "recepcao")
    assert recepcao.get(reverse("orcamentos:procedimentos")).status_code == 200
    assert recepcao.get(reverse("orcamentos:procedimento_novo")).status_code == 403
    admin = entrar(cenario, "admin")
    url = reverse("orcamentos:procedimento_novo")
    assert (
        admin.post(url, {"nome": "Clareamento", "valor": "900", "ativo": "on"}).status_code == 302
    )
    assert "Já existe" in admin.post(url, {"nome": "Clareamento", "valor": "1"}).content.decode()


def test_exclusao_definitiva_apaga_os_orcamentos(cenario):
    admin = entrar(cenario, "admin")
    orcamento = criar_orcamento(cenario, admin)
    incluir(admin, orcamento, procedimento=cenario["canal"].pk, dentes="11")
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.filter(pk=cenario["paciente"].pk).update(arquivado=True)
    admin.post(reverse("pacientes:excluir", args=[cenario["paciente"].pk]))
    with usar_clinica(cenario["clinica"]):
        assert not Orcamento.objects.exists() and not ItemOrcamento.objects.exists()


def test_orcamento_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    orcamento = criar_orcamento(cenario, entrar(cenario, "recepcao"))
    outro = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert outro.get(reverse("orcamentos:detalhe", args=[orcamento.pk])).status_code == 404
