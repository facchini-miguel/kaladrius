"""Suppliers (decision 093): register, pick on a payable, history. Fictitious data only."""

import pytest
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modules import configurar
from apps.finance.models import Category, Entry, Supplier

pytestmark = pytest.mark.django_db

CNPJ = "11222333000181"


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fornecedores", clinica_a, Papel.ADMIN))


@pytest.fixture
def fornecedor(clinica_a):
    with usar_clinica(clinica_a):
        return Supplier.objects.create(name="Dental Fictícia", cpf_cnpj=CNPJ)


def dados(**extra):
    return {"kind": "PJ", "name": "Laboratório Fictício", "active": "on", **extra}


def despesa(clinic, **extra):
    with usar_clinica(clinic):
        categoria = Category.objects.filter(kind=Category.Tipo.DESPESA).first()
    return {
        "fornecedor": "",
        "pessoa": "",
        "description": "Material fictício",
        "categoria": categoria.pk,
        "amount": "450",
        "modo": "dividir",
        "parcelas": 3,
        "primeiro_vencimento": "2031-01-10",
        "notes": "",
        **extra,
    }


def test_cadastro_normaliza_documento_e_contatos(clinica_a, admin):
    resposta = admin.post(
        reverse("finance:supplier_new"),
        dados(cpf_cnpj="11.222.333/0001-81", phone="(48) 3333-4444", whatsapp="48 99999-0000"),
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        criado = Supplier.objects.get()
    assert (criado.cpf_cnpj, criado.phone, criado.whatsapp) == (
        CNPJ,
        "4833334444",
        "48999990000",
    )
    assert resposta.url == reverse("finance:supplier", args=[criado.pk])


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"cpf_cnpj": "11.222.333/0001-00"}, "cpf_cnpj"),
        ({"kind": "PF", "cpf_cnpj": "111.111.111-11"}, "cpf_cnpj"),
        ({"phone": "1234"}, "phone"),
        ({"name": ""}, "name"),
    ],
)
def test_validacoes_do_cadastro(extra, campo, admin):
    resposta = admin.post(reverse("finance:supplier_new"), dados(**extra))
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors


def test_documento_repetido_e_recusado(fornecedor, admin):
    resposta = admin.post(reverse("finance:supplier_new"), dados(cpf_cnpj=CNPJ))
    assert "cpf_cnpj" in resposta.context["form"].errors
    editar = admin.post(
        reverse("finance:supplier_edit", args=[fornecedor.pk]),
        dados(name="Dental Fictícia Renomeada", cpf_cnpj=CNPJ),
    )
    assert editar.status_code == 302


def test_despesa_com_fornecedor_guarda_o_nome_e_aparece_na_ficha(clinica_a, fornecedor, admin):
    pagina = admin.get(reverse("finance:expense_new") + f"?fornecedor={fornecedor.pk}")
    assert pagina.context["form"]["fornecedor"].value() == str(fornecedor.pk)
    resposta = admin.post(
        reverse("finance:expense_new"), despesa(clinica_a, fornecedor=fornecedor.pk)
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        entry = Entry.objects.get()
    assert entry.fornecedor == fornecedor
    assert entry.pessoa == "Dental Fictícia"
    ficha = admin.get(reverse("finance:supplier", args=[fornecedor.pk]))
    assert len(ficha.context["parcelas"]) == 3
    assert str(ficha.context["em_aberto"]) == "450.00"
    lista = admin.get(reverse("finance:payables")).content.decode()
    assert reverse("finance:supplier", args=[fornecedor.pk]) in lista
    assert admin.get(reverse("finance:payables") + "?q=Dental").context["pagina"].paginator.count


def test_despesa_avulsa_sem_fornecedor_continua_valendo(clinica_a, admin):
    resposta = admin.post(reverse("finance:expense_new"), despesa(clinica_a, pessoa="Feira"))
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        entry = Entry.objects.get()
    assert (entry.fornecedor, entry.pessoa) == (None, "Feira")


def test_despesa_exige_fornecedor_ou_nome(clinica_a, admin):
    resposta = admin.post(reverse("finance:expense_new"), despesa(clinica_a))
    assert resposta.status_code == 200
    assert "fornecedor" in resposta.context["form"].errors


def test_fornecedor_inativo_some_da_despesa_mas_fica_na_lista(clinica_a, fornecedor, admin):
    with usar_clinica(clinica_a):
        fornecedor.active = False
        fornecedor.save()
    form = admin.get(reverse("finance:expense_new")).context["form"]
    with usar_clinica(clinica_a):
        assert fornecedor not in form.fields["fornecedor"].queryset
    assert fornecedor in admin.get(reverse("finance:suppliers")).context["pagina"]


def test_busca_por_nome_e_documento(fornecedor, admin):
    url = reverse("finance:suppliers")
    assert list(admin.get(url, {"q": "dental ficticia"}).context["pagina"]) == [fornecedor]
    assert list(admin.get(url, {"q": "11.222.333"}).context["pagina"]) == [fornecedor]
    assert list(admin.get(url, {"q": "outro"}).context["pagina"]) == []


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_quem_cuida_do_financeiro_ve_fornecedores(
    papel, fornecedor, clinica_a, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("sem_financeiro", clinica_a, papel))
    for url in (
        reverse("finance:suppliers"),
        reverse("finance:supplier", args=[fornecedor.pk]),
        reverse("finance:supplier_new"),
    ):
        assert cliente.get(url).status_code == 403, url


def test_perfil_financeiro_cadastra_fornecedor(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("financeiro_fornecedores", clinica_a, Papel.FINANCEIRO))
    assert cliente.post(reverse("finance:supplier_new"), dados()).status_code == 302


def test_fornecedores_somem_com_o_financeiro_desligado(clinica_a, fornecedor, admin):
    assert reverse("finance:suppliers") in admin.get(reverse("home")).content.decode()
    configurar(
        clinica_a,
        MODULOS_GERAIS
        - {ModuloClinico.FINANCEIRO, ModuloClinico.ORCAMENTOS, ModuloClinico.PESSOAL},
    )
    assert admin.get(reverse("finance:suppliers")).status_code == 403
    assert reverse("finance:suppliers") not in admin.get(reverse("home")).content.decode()


def test_fornecedor_de_outra_clinica_nao_aparece(clinica_b, fornecedor, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert cliente.get(reverse("finance:supplier", args=[fornecedor.pk])).status_code == 404
