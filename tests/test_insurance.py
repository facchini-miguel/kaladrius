"""Health plans and insurance of each country (decision 125): the insurer's registry, the card's
fields and the procedure coding follow the clinic's country."""

import re

import pytest
from django.urls import reverse

from apps.core.countries import PAISES
from apps.core.isolation import usar_clinica
from apps.estimates.models import Procedimento
from apps.health_plans import insurance
from apps.health_plans.models import Carteirinha, Convenio
from tests.test_estimates import cenario, criar_orcamento, entrar, incluir  # noqa: F401
from tests.test_health_plans import admin, carteirinha, convenio, paciente  # noqa: F401

pytestmark = pytest.mark.django_db


def mudar_pais(clinica, pais):
    clinica.pais = pais
    clinica.save()


def test_cada_pais_tem_as_suas_regras():
    assert set(insurance.SEGUROS) == set(PAISES)
    for pais, regras in insurance.SEGUROS.items():
        for codigo in (regras.registro, regras.procedimento):
            if codigo and codigo.padrao:
                # Every format has an example, and the example follows it.
                assert re.fullmatch(codigo.padrao, codigo.exemplo), pais


def test_codigo_limpo_e_conferido():
    cdt = insurance.do_pais("US").procedimento
    assert cdt.limpar(" d1110 ") == "D1110"
    with pytest.raises(Exception, match="CDT"):
        cdt.limpar("1110")
    assert insurance.do_pais("BR").registro.limpar("00.000-2") == "000002"
    assert insurance.do_pais("AR").registro.limpar("1-0040-7") == "100407"  # free format


def test_registro_da_operadora_por_pais(clinica_a, admin):  # noqa: F811
    form = admin.get(reverse("convenios:novo")).context["form"]
    assert str(form.fields["registro"].label) == "Registro da operadora (ANS)"
    mudar_pais(clinica_a, "US")
    form = admin.get(reverse("convenios:novo")).context["form"]
    assert str(form.fields["registro"].label) == "Registro da operadora (Payer ID)"
    assert "dental insurance carriers" in str(form.fields["nome"].help_text)
    recusado = admin.post(reverse("convenios:novo"), {"nome": "Fictitious Dental", "registro": "1"})
    assert "registro" in recusado.context["form"].errors
    dados = {"nome": "Fictitious Dental", "registro": "ab-123", "ativo": "on"}
    assert admin.post(reverse("convenios:novo"), dados).status_code == 302
    with usar_clinica(clinica_a):
        assert Convenio.objects.get().registro == "AB123"
    assert "Payer ID" in admin.get(reverse("convenios:lista")).content.decode()
    # The United Kingdom has no insurer registry: no field and no column.
    mudar_pais(clinica_a, "GB")
    assert "registro" not in admin.get(reverse("convenios:novo")).context["form"].fields
    assert "Registro da operadora" not in admin.get(reverse("convenios:lista")).content.decode()


def test_campos_da_carteirinha_por_pais(clinica_a, paciente, convenio, admin):  # noqa: F811
    url = reverse("convenios:carteirinha_nova", args=[paciente.pk])
    campos = admin.get(url).context["form"].fields
    assert "grupo" not in campos and "beneficiario" not in campos  # Brazil
    mudar_pais(clinica_a, "US")
    campos = admin.get(url).context["form"].fields
    assert str(campos["numero"].label) == "Número da carteirinha (Member ID)"
    assert str(campos["grupo"].label) == "Número do grupo (Group number)"
    assert "beneficiario" not in campos
    dados = carteirinha(convenio, numero="W123456789", grupo="G-100")
    assert admin.post(url, dados).status_code == 302
    with usar_clinica(clinica_a):
        assert Carteirinha.objects.get().grupo == "G-100"
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    assert "W123456789" in ficha and "G-100" in ficha
    mudar_pais(clinica_a, "ZA")
    campos = admin.get(url).context["form"].fields
    assert str(campos["beneficiario"].label) == "Código do beneficiário (dependant code)"


def test_codigo_do_procedimento_vai_para_o_orcamento(cenario):  # noqa: F811
    clinica = cenario["clinica"]
    cliente = entrar(cenario, "admin")
    url = reverse("orcamentos:procedimento_editar", args=[cenario["restauracao"].pk])
    dados = {"nome": "Restauração", "valor": "250,00", "categoria": "", "ativo": "on"}
    form = cliente.get(url).context["form"]
    assert str(form.fields["codigo"].label) == "Código (TUSS)"
    assert "codigo" in cliente.post(url, {**dados, "codigo": "123"}).context["form"].errors
    assert cliente.post(url, {**dados, "codigo": "8510.0099"}).status_code == 302
    with usar_clinica(clinica):
        assert Procedimento.objects.get(nome="Restauração").codigo == "85100099"
    orcamento = criar_orcamento(cenario, cliente)
    incluir(cliente, orcamento, procedimento=cenario["restauracao"].pk)
    with usar_clinica(clinica):
        assert orcamento.itens.get().codigo == "85100099"
    impresso = cliente.get(reverse("orcamentos:imprimir", args=[orcamento.pk])).content.decode()
    assert "85100099 · Restauração" in impresso
    # A country without one coding: just "Código", free text.
    mudar_pais(clinica, "UY")
    form = cliente.get(url).context["form"]
    assert str(form.fields["codigo"].label) == "Código"
