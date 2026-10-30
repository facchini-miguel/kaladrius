"""Suppliers (decision 093): register, pick on a payable, history. Fictitious data only."""

import pytest
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modulos import configurar
from apps.financeiro.models import Categoria, Fornecedor, Lancamento

pytestmark = pytest.mark.django_db

CNPJ = "11222333000181"


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fornecedores", clinica_a, Papel.ADMIN))


@pytest.fixture
def fornecedor(clinica_a):
    with usar_clinica(clinica_a):
        return Fornecedor.objects.create(nome="Dental Fictícia", cpf_cnpj=CNPJ)


def dados(**extra):
    return {"tipo": "PJ", "nome": "Laboratório Fictício", "ativo": "on", **extra}


def despesa(clinica, **extra):
    with usar_clinica(clinica):
        categoria = Categoria.objects.filter(tipo=Categoria.Tipo.DESPESA).first()
    return {
        "fornecedor": "",
        "pessoa": "",
        "descricao": "Material fictício",
        "categoria": categoria.pk,
        "valor": "450",
        "modo": "dividir",
        "parcelas": 3,
        "primeiro_vencimento": "2031-01-10",
        "observacoes": "",
        **extra,
    }


def test_cadastro_normaliza_documento_e_contatos(clinica_a, admin):
    resposta = admin.post(
        reverse("financeiro:fornecedor_novo"),
        dados(cpf_cnpj="11.222.333/0001-81", telefone="(48) 3333-4444", whatsapp="48 99999-0000"),
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        criado = Fornecedor.objects.get()
    assert (criado.cpf_cnpj, criado.telefone, criado.whatsapp) == (
        CNPJ,
        "4833334444",
        "48999990000",
    )
    assert resposta.url == reverse("financeiro:fornecedor", args=[criado.pk])


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"cpf_cnpj": "11.222.333/0001-00"}, "cpf_cnpj"),
        ({"tipo": "PF", "cpf_cnpj": "111.111.111-11"}, "cpf_cnpj"),
        ({"telefone": "1234"}, "telefone"),
        ({"nome": ""}, "nome"),
    ],
)
def test_validacoes_do_cadastro(extra, campo, admin):
    resposta = admin.post(reverse("financeiro:fornecedor_novo"), dados(**extra))
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors


def test_documento_repetido_e_recusado(fornecedor, admin):
    resposta = admin.post(reverse("financeiro:fornecedor_novo"), dados(cpf_cnpj=CNPJ))
    assert "cpf_cnpj" in resposta.context["form"].errors
    editar = admin.post(
        reverse("financeiro:fornecedor_editar", args=[fornecedor.pk]),
        dados(nome="Dental Fictícia Renomeada", cpf_cnpj=CNPJ),
    )
    assert editar.status_code == 302


def test_despesa_com_fornecedor_guarda_o_nome_e_aparece_na_ficha(clinica_a, fornecedor, admin):
    pagina = admin.get(reverse("financeiro:despesa_nova") + f"?fornecedor={fornecedor.pk}")
    assert pagina.context["form"]["fornecedor"].value() == str(fornecedor.pk)
    resposta = admin.post(
        reverse("financeiro:despesa_nova"), despesa(clinica_a, fornecedor=fornecedor.pk)
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        lancamento = Lancamento.objects.get()
    assert lancamento.fornecedor == fornecedor
    assert lancamento.pessoa == "Dental Fictícia"
    ficha = admin.get(reverse("financeiro:fornecedor", args=[fornecedor.pk]))
    assert len(ficha.context["parcelas"]) == 3
    assert str(ficha.context["em_aberto"]) == "450.00"
    lista = admin.get(reverse("financeiro:pagar")).content.decode()
    assert reverse("financeiro:fornecedor", args=[fornecedor.pk]) in lista
    assert admin.get(reverse("financeiro:pagar") + "?q=Dental").context["pagina"].paginator.count


def test_despesa_avulsa_sem_fornecedor_continua_valendo(clinica_a, admin):
    resposta = admin.post(reverse("financeiro:despesa_nova"), despesa(clinica_a, pessoa="Feira"))
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        lancamento = Lancamento.objects.get()
    assert (lancamento.fornecedor, lancamento.pessoa) == (None, "Feira")


def test_despesa_exige_fornecedor_ou_nome(clinica_a, admin):
    resposta = admin.post(reverse("financeiro:despesa_nova"), despesa(clinica_a))
    assert resposta.status_code == 200
    assert "fornecedor" in resposta.context["form"].errors


def test_fornecedor_inativo_some_da_despesa_mas_fica_na_lista(clinica_a, fornecedor, admin):
    with usar_clinica(clinica_a):
        fornecedor.ativo = False
        fornecedor.save()
    form = admin.get(reverse("financeiro:despesa_nova")).context["form"]
    with usar_clinica(clinica_a):
        assert fornecedor not in form.fields["fornecedor"].queryset
    assert fornecedor in admin.get(reverse("financeiro:fornecedores")).context["pagina"]


def test_busca_por_nome_e_documento(fornecedor, admin):
    url = reverse("financeiro:fornecedores")
    assert list(admin.get(url, {"q": "dental ficticia"}).context["pagina"]) == [fornecedor]
    assert list(admin.get(url, {"q": "11.222.333"}).context["pagina"]) == [fornecedor]
    assert list(admin.get(url, {"q": "outro"}).context["pagina"]) == []


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_quem_cuida_do_financeiro_ve_fornecedores(
    papel, fornecedor, clinica_a, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("sem_financeiro", clinica_a, papel))
    for url in (
        reverse("financeiro:fornecedores"),
        reverse("financeiro:fornecedor", args=[fornecedor.pk]),
        reverse("financeiro:fornecedor_novo"),
    ):
        assert cliente.get(url).status_code == 403, url


def test_perfil_financeiro_cadastra_fornecedor(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("financeiro_fornecedores", clinica_a, Papel.FINANCEIRO))
    assert cliente.post(reverse("financeiro:fornecedor_novo"), dados()).status_code == 302


def test_fornecedores_somem_com_o_financeiro_desligado(clinica_a, fornecedor, admin):
    assert reverse("financeiro:fornecedores") in admin.get(reverse("inicio")).content.decode()
    configurar(
        clinica_a,
        MODULOS_GERAIS
        - {ModuloClinico.FINANCEIRO, ModuloClinico.ORCAMENTOS, ModuloClinico.PESSOAL},
    )
    assert admin.get(reverse("financeiro:fornecedores")).status_code == 403
    assert reverse("financeiro:fornecedores") not in admin.get(reverse("inicio")).content.decode()


def test_fornecedor_de_outra_clinica_nao_aparece(clinica_b, fornecedor, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    assert cliente.get(reverse("financeiro:fornecedor", args=[fornecedor.pk])).status_code == 404
