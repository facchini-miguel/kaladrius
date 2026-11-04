"""Cost centers (decision 095): register, optional on entries, reports. Fictitious data only."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modules import configurar
from apps.finance import services
from apps.finance.models import Category, CostCenter, Entry, FinancialAccount
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
URL = "finance:catalog"


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_centros", clinica_a, Papel.ADMIN))


@pytest.fixture
def centro(clinica_a):
    with usar_clinica(clinica_a):
        return CostCenter.objects.create(nome="Ortodontia")


def despesa(clinic, **extra):
    with usar_clinica(clinic):
        categoria = Category.objects.get(nome="Aluguel")
    return {
        "pessoa": "Imobiliária fictícia",
        "descricao": "Aluguel",
        "categoria": categoria.pk,
        "valor": "1000",
        "modo": "dividir",
        "parcelas": 1,
        "primeiro_vencimento": HOJE.isoformat(),
        "observacoes": "",
        **extra,
    }


def test_cadastro_e_nome_repetido(clinica_a, admin):
    url = reverse("finance:catalog_new", args=["cost-centers"])
    assert admin.post(url, {"nome": " Consultório 1 ", "ativo": "on"}).status_code == 302
    with usar_clinica(clinica_a):
        assert CostCenter.objects.get().nome == "Consultório 1"
    repetido = admin.post(url, {"nome": "consultório 1", "ativo": "on"})
    assert "nome" in repetido.context["form"].errors
    lista = admin.get(reverse(URL, args=["cost-centers"])).content.decode()
    assert "Consultório 1" in lista and "Ativo" in lista


def test_campo_so_aparece_com_centro_cadastrado(clinica_a, admin):
    for rota in ("finance:entry_new", "finance:expense_new"):
        assert "centro_custo" not in admin.get(reverse(rota)).context["form"].fields
    with usar_clinica(clinica_a):
        inativo = CostCenter.objects.create(nome="Desativado", ativo=False)
    assert "centro_custo" not in admin.get(reverse("finance:expense_new")).context["form"].fields
    with usar_clinica(clinica_a):
        CostCenter.objects.create(nome="Ativo")
    campo = admin.get(reverse("finance:expense_new")).context["form"].fields["centro_custo"]
    with usar_clinica(clinica_a):
        assert inativo not in campo.queryset and campo.queryset.count() == 1


def test_lancamentos_guardam_o_centro(clinica_a, centro, admin):
    assert (
        admin.post(
            reverse("finance:expense_new"), despesa(clinica_a, centro_custo=centro.pk)
        ).status_code
        == 302
    )
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(nome="Paciente fictício do centro")
        receita = Category.objects.get(nome="Tratamento")
    resposta = admin.post(
        reverse("finance:entry_new"),
        {
            "patient": patient.pk,
            "pessoa": "",
            "descricao": "Aparelho",
            "categoria": receita.pk,
            "centro_custo": centro.pk,
            "practitioner": "",
            "valor_total": "500",
            "parcelas": 1,
            "primeiro_vencimento": HOJE.isoformat(),
            "observacoes": "",
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert Entry.objects.filter(centro_custo=centro).count() == 2
        lancamento = Entry.objects.get(tipo=Entry.Tipo.PAGAR)
    pagina = admin.get(reverse("finance:entry", args=[lancamento.pk])).content.decode()
    assert "Ortodontia" in pagina
    # Without a center the entry still saves (the field is optional).
    assert admin.post(reverse("finance:expense_new"), despesa(clinica_a)).status_code == 302


def test_relatorio_por_centro_de_custo(clinica_a, centro, admin):
    with usar_clinica(clinica_a):
        aluguel = Category.objects.get(nome="Aluguel")
        caixa = FinancialAccount.objects.get(nome="Caixa")
        for valor, centro_custo in ((Decimal("300"), centro), (Decimal("200"), None)):
            lancamento = services.criar_lancamento(
                clinic=clinica_a,
                tipo=Entry.Tipo.PAGAR,
                pessoa="Fornecedor fictício",
                descricao="Compra",
                categoria=aluguel,
                centro_custo=centro_custo,
                valor_total=valor,
                parcelas=1,
                primeiro_vencimento=HOJE,
                user=None,
            )
            parcela = lancamento.parcelas.get()
            services.receber(parcela, user=None, valor=parcela.valor, forma="pix", conta=caixa)
    relatorio = admin.get(reverse("finance:reports")).context["relatorio"]
    assert relatorio["centros"]
    assert {nome: str(total) for nome, total in relatorio["despesas_por_centro"]} == {
        "Ortodontia": "300.00",
        "Sem centro de custo": "200.00",
    }
    assert (
        "Despesas pagas por centro de custo"
        in admin.get(reverse("finance:reports")).content.decode()
    )


def test_relatorio_sem_centros_nao_mostra_os_quadros(admin):
    relatorio = admin.get(reverse("finance:reports"))
    assert not relatorio.context["relatorio"]["centros"]
    assert "por centro de custo" not in relatorio.content.decode()


def test_recepcao_nao_cadastra(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_centros", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(reverse(URL, args=["cost-centers"])).status_code == 403


def test_some_com_o_financeiro_desligado(clinica_a, admin):
    lista = reverse(URL, args=["cost-centers"])
    assert lista in admin.get(reverse("home")).content.decode()
    configurar(
        clinica_a,
        MODULOS_GERAIS
        - {ModuloClinico.FINANCEIRO, ModuloClinico.ORCAMENTOS, ModuloClinico.PESSOAL},
    )
    assert admin.get(lista).status_code == 403
    assert lista not in admin.get(reverse("home")).content.decode()
