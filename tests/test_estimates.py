"""Procedure price list and treatment estimates (0.18.0)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.estimates import services
from apps.estimates.models import Estimate, EstimateItem, Procedure
from apps.finance.models import Category, Entry, FinancialAccount
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db
HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Joana Sorriso")
        tratamento = Category.objects.get(name="Tratamento")
        canal = Procedure.objects.create(
            name="Tratamento de canal", amount=Decimal("1200"), category=tratamento
        )
        restauracao = Procedure.objects.create(name="Restauração", amount=Decimal("250"))
    return {
        "clinic": clinica_a,
        "patient": patient,
        "canal": canal,
        "restauracao": restauracao,
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "practitioner": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def criar_orcamento(cenario, cliente):
    resposta = cliente.post(
        reverse("estimates:new"),
        {
            "patient": cenario["patient"].pk,
            "practitioner": "",
            "date": HOJE.isoformat(),
            "valid_until": HOJE.isoformat(),
            "notes": "",
        },
    )
    with usar_clinica(cenario["clinic"]):
        orcamento = Estimate.objects.latest("pk")
    assert resposta.url == reverse("estimates:detail", args=[orcamento.pk])
    return orcamento


def incluir(cliente, orcamento, **dados):
    return cliente.post(
        reverse("estimates:item_add", args=[orcamento.pk]),
        {
            "description": "",
            "dentes": "",
            "faces": "",
            "quantidade": 1,
            "valor_unitario": "",
            **dados,
        },
    )


def test_profissional_monta_orcamento_com_dentes(cenario):
    cliente = entrar(cenario, "practitioner")
    orcamento = criar_orcamento(cenario, cliente)
    # Description and price come from the price list; teeth are normalized.
    incluir(
        cliente, orcamento, procedimento=cenario["restauracao"].pk, dentes="36, 11,11", quantidade=2
    )
    incluir(cliente, orcamento, description="Moldagem", valor_unitario="80,00")
    with usar_clinica(cenario["clinic"]):
        itens = list(orcamento.itens.order_by("pk"))
        orcamento.refresh_from_db()
        assert orcamento.total == Decimal("580.00")
        assert orcamento.dentes == [11, 36]
    assert (itens[0].description, itens[0].dentes, itens[0].valor_unitario) == (
        "Restauração",
        "11,36",
        Decimal("250.00"),
    )
    assert itens[0].dentes_exibicao == "11, 36"
    pagina = cliente.get(reverse("estimates:detail", args=[orcamento.pk])).content.decode()
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
    with usar_clinica(cenario["clinic"]):
        assert not orcamento.itens.exists()


def test_quem_escreve_o_orcamento_da_desconto(cenario):
    # Front desk, practitioner and administrator (0.27.1, decision 074).
    recepcao = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, recepcao)
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk)
    url = reverse("estimates:discount", args=[orcamento.pk])
    assert recepcao.get(reverse("estimates:detail", args=[orcamento.pk])).context["desconto_form"]
    recepcao.post(url, {"discount": "5000"})  # more than the total: refused
    orcamento.refresh_from_db()
    assert orcamento.discount == 0
    recepcao.post(url, {"discount": "200"})
    orcamento.refresh_from_db()
    assert orcamento.discount == Decimal("200.00")
    for quem, amount in [("practitioner", "150"), ("admin", "100")]:
        entrar(cenario, quem).post(url, {"discount": amount})
        orcamento.refresh_from_db()
        assert orcamento.discount == Decimal(amount)


def test_aprovar_vira_lancamento_a_receber(cenario):
    recepcao = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, recepcao)
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk)
    with usar_clinica(cenario["clinic"]):
        Estimate.objects.filter(pk=orcamento.pk).update(discount=Decimal("200"))
        cash_register = FinancialAccount.objects.get(name="Caixa")
    url = reverse("estimates:approve", args=[orcamento.pk])
    # The category comes from the first procedure.
    assert recepcao.get(url).context["form"].initial["category"] == cenario["canal"].category
    resposta = recepcao.post(
        url,
        {
            "parcelas": 4,
            "primeiro_vencimento": HOJE.isoformat(),
            "category": cenario["canal"].category.pk,
            "recebido_agora": "on",
            "method": "pix",
            "account": cash_register.pk,
        },
    )
    orcamento.refresh_from_db()
    entry = orcamento.entry
    assert resposta.url == reverse("finance:entry", args=[entry.pk])
    assert orcamento.status == Estimate.Situacao.APROVADO
    assert (entry.kind, entry.total_amount) == (
        Entry.Tipo.RECEBER,
        Decimal("1000.00"),
    )
    with usar_clinica(cenario["clinic"]):
        assert entry.parcelas.count() == 4
        assert entry.patient == cenario["patient"]
    # Once approved, nothing changes any more.
    incluir(recepcao, orcamento, procedimento=cenario["restauracao"].pk)
    with usar_clinica(cenario["clinic"]):
        assert orcamento.itens.count() == 1
    assert recepcao.post(reverse("estimates:decline", args=[orcamento.pk])).status_code == 302
    orcamento.refresh_from_db()
    assert orcamento.status == Estimate.Situacao.APROVADO


def test_profissional_nao_aprova(cenario):
    cliente = entrar(cenario, "practitioner")
    orcamento = criar_orcamento(cenario, cliente)
    assert cliente.get(reverse("estimates:approve", args=[orcamento.pk])).status_code == 403
    assert not cliente.get(reverse("estimates:detail", args=[orcamento.pk])).context["pode_aprovar"]


def test_recusar_e_imprimir(cenario):
    cliente = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, cliente)
    incluir(cliente, orcamento, procedimento=cenario["canal"].pk, dentes="46")
    pagina = cliente.get(reverse("estimates:print", args=[orcamento.pk])).content.decode()
    assert "ORÇAMENTO" in pagina and "Joana Sorriso" in pagina and "selecionado" in pagina
    cliente.post(reverse("estimates:decline", args=[orcamento.pk]))
    orcamento.refresh_from_db()
    assert orcamento.status == Estimate.Situacao.RECUSADO
    # Deciding again (e.g. a stale page approving it meanwhile) is refused.
    with usar_clinica(cenario["clinic"]), pytest.raises(ValidationError):
        services.recusar(orcamento, user=None)
    lista = cliente.get(reverse("estimates:list"), {"status": "recusado"})
    assert list(lista.context["pagina"]) == [orcamento]


def test_ficha_mostra_orcamentos_e_arquivado_some(cenario):
    cliente = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, cliente)
    ficha = cliente.get(reverse("patients:record", args=[cenario["patient"].pk]))
    assert ficha.context["orcamentos"] == [orcamento]
    with usar_clinica(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    assert cliente.get(reverse("estimates:detail", args=[orcamento.pk])).status_code == 404


def test_tabela_de_procedimentos_so_o_admin_altera(cenario):
    recepcao = entrar(cenario, "recepcao")
    assert recepcao.get(reverse("estimates:procedures")).status_code == 200
    assert recepcao.get(reverse("estimates:procedure_new")).status_code == 403
    admin = entrar(cenario, "admin")
    url = reverse("estimates:procedure_new")
    assert (
        admin.post(url, {"name": "Clareamento", "amount": "900", "active": "on"}).status_code == 302
    )
    assert "Já existe" in admin.post(url, {"name": "Clareamento", "amount": "1"}).content.decode()


def test_exclusao_definitiva_apaga_os_orcamentos(cenario):
    admin = entrar(cenario, "admin")
    orcamento = criar_orcamento(cenario, admin)
    incluir(admin, orcamento, procedimento=cenario["canal"].pk, dentes="11")
    with usar_clinica(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    admin.post(reverse("patients:delete", args=[cenario["patient"].pk]))
    with usar_clinica(cenario["clinic"]):
        assert not Estimate.objects.exists() and not EstimateItem.objects.exists()


def test_orcamento_de_outra_clinica_da_404(cenario, clinica_b, criar_usuario, cliente_de):
    orcamento = criar_orcamento(cenario, entrar(cenario, "recepcao"))
    outro = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert outro.get(reverse("estimates:detail", args=[orcamento.pk])).status_code == 404


def test_odontograma_so_na_area_odontologia(cenario):
    # Decision 080: teeth and faces belong to the dental module.
    from apps.core.models import Clinic

    recepcao = entrar(cenario, "recepcao")
    orcamento = criar_orcamento(cenario, recepcao)
    detalhe = reverse("estimates:detail", args=[orcamento.pk])
    pagina = recepcao.get(detalhe)
    assert pagina.context["mostrar_dentes"] and "odontograma" in pagina.content.decode()
    assert "dentes" in pagina.context["item_form"].fields

    from apps.core.models import MODULOS_GERAIS
    from apps.core.modules import configurar

    configurar(cenario["clinic"], {*MODULOS_GERAIS, Clinic.Area.MEDICINA})
    pagina = recepcao.get(detalhe)
    assert not pagina.context["mostrar_dentes"] and "odontograma" not in pagina.content.decode()
    assert "dentes" not in pagina.context["item_form"].fields
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk, dentes="11", faces="V")
    with usar_clinica(cenario["clinic"]):
        assert not orcamento.itens.exists()  # forged fields are rejected, not discarded
    configurar(cenario["clinic"], {*MODULOS_GERAIS, Clinic.Area.ODONTOLOGIA})
    incluir(recepcao, orcamento, procedimento=cenario["canal"].pk, dentes="11", faces="V")
    configurar(cenario["clinic"], {*MODULOS_GERAIS, Clinic.Area.MEDICINA})
    pagina = recepcao.get(detalhe)
    assert pagina.context["mostrar_dentes"] and "11" in pagina.content.decode()
    impressao = recepcao.get(reverse("estimates:print", args=[orcamento.pk]))
    assert impressao.context["mostrar_dentes"]
