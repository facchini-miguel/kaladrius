"""Health plans and patients' cards (decision 094). Fictitious data only."""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.convenios.models import Carteirinha, Convenio
from apps.core.isolamento import ClinicaDiferente, usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modulos import configurar
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_convenios", clinica_a, Papel.ADMIN))


@pytest.fixture
def paciente(clinica_a):
    with usar_clinica(clinica_a):
        return Paciente.objects.create(nome="Paciente fictícia do convênio")


@pytest.fixture
def convenio(clinica_a):
    with usar_clinica(clinica_a):
        return Convenio.objects.create(nome="Saúde Exemplo", registro_ans="000001")


def carteirinha(convenio, **extra):
    return {"convenio": convenio.pk, "plano": "Básico", "numero": "123", "ativa": "on", **extra}


def test_cadastro_do_convenio(clinica_a, admin):
    resposta = admin.post(
        reverse("convenios:novo"),
        {"nome": " Plano Fictício ", "registro_ans": "00.000-2", "telefone": "", "ativo": "on"},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        criado = Convenio.objects.get()
    assert (criado.nome, criado.registro_ans) == ("Plano Fictício", "000002")
    assert "Plano Fictício" in admin.get(reverse("convenios:lista")).content.decode()


@pytest.mark.parametrize(
    ("dados", "campo"),
    [
        ({"nome": "saúde exemplo"}, "nome"),
        ({"nome": "Outro", "registro_ans": "123"}, "registro_ans"),
        ({"nome": "Outro", "telefone": "99"}, "telefone"),
    ],
)
def test_validacoes_do_convenio(dados, campo, convenio, admin):
    resposta = admin.post(reverse("convenios:novo"), dados)
    assert campo in resposta.context["form"].errors


def test_carteirinha_na_ficha_com_validade(clinica_a, paciente, convenio, admin):
    url = reverse("convenios:carteirinha_nova", args=[paciente.pk])
    vencida = (HOJE - datetime.timedelta(days=1)).isoformat()
    resposta = admin.post(url, carteirinha(convenio, numero=" 0099 ", validade=vencida))
    assert resposta.url == reverse("pacientes:ficha", args=[paciente.pk])
    with usar_clinica(clinica_a):
        criada = Carteirinha.objects.get()
    assert (criada.paciente, criada.numero, criada.vencida) == (paciente, "0099", True)
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    assert "Saúde Exemplo" in ficha and "Vencida" in ficha
    # The same card number cannot belong to two patients of the same plan.
    with usar_clinica(clinica_a):
        outro = Paciente.objects.create(nome="Outra paciente fictícia")
    repetida = admin.post(
        reverse("convenios:carteirinha_nova", args=[outro.pk]), carteirinha(convenio, numero="0099")
    )
    assert "numero" in repetida.context["form"].errors
    editar = admin.post(
        reverse("convenios:carteirinha_editar", args=[criada.pk]),
        carteirinha(convenio, numero="0099", plano="Apartamento"),
    )
    assert editar.status_code == 302


def test_paciente_sem_carteirinha_e_particular(paciente, admin):
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    assert "Particular" in ficha


def test_convenio_inativo_some_da_carteirinha_nova_mas_fica_na_existente(
    clinica_a, paciente, convenio, admin
):
    with usar_clinica(clinica_a):
        existente = Carteirinha.objects.create(paciente=paciente, convenio=convenio, numero="1")
        convenio.ativo = False
        convenio.save()
    nova = admin.get(reverse("convenios:carteirinha_nova", args=[paciente.pk])).context["form"]
    antiga = admin.get(reverse("convenios:carteirinha_editar", args=[existente.pk])).context["form"]
    with usar_clinica(clinica_a):
        assert convenio not in nova.fields["convenio"].queryset
        assert convenio in antiga.fields["convenio"].queryset


@pytest.mark.parametrize(
    ("papel", "ver", "criar"),
    [
        (Papel.RECEPCAO, 200, 200),
        (Papel.PROFISSIONAL, 200, 403),
        (Papel.FINANCEIRO, 200, 403),
    ],
)
def test_permissoes_por_papel(
    papel, ver, criar, clinica_a, paciente, convenio, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("papel_convenios", clinica_a, papel))
    assert cliente.get(reverse("convenios:lista")).status_code == ver
    assert cliente.get(reverse("convenios:carteirinha_nova", args=[paciente.pk])).status_code == (
        criar
    )


def test_modulo_desligado(clinica_a, paciente, convenio, admin):
    assert reverse("convenios:lista") in admin.get(reverse("inicio")).content.decode()
    configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.CONVENIOS})
    assert admin.get(reverse("convenios:lista")).status_code == 403
    assert reverse("convenios:lista") not in admin.get(reverse("inicio")).content.decode()
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk]))
    assert ficha.context.get("carteirinhas") is None


def test_carteirinha_nao_liga_paciente_e_convenio_de_clinicas_diferentes(
    clinica_a, clinica_b, convenio
):
    with usar_clinica(clinica_b):
        de_outra = Paciente.objects.create(nome="Paciente fictício B")
    with usar_clinica(clinica_b), pytest.raises(ClinicaDiferente):
        Carteirinha.objects.create(paciente=de_outra, convenio=convenio, numero="9")


def test_exclusao_lgpd_apaga_as_carteirinhas(clinica_a, paciente, convenio, admin):
    with usar_clinica(clinica_a):
        criada = Carteirinha.objects.create(
            paciente=paciente, convenio=convenio, numero="CARTEIRINHA-SIGILOSA"
        )
        paciente.arquivado = True
        paciente.save()
    resposta = admin.post(reverse("pacientes:excluir", args=[paciente.pk]))
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert not Carteirinha.objects.exists()
        assert Convenio.objects.filter(pk=convenio.pk).exists()
    registros = RegistroAuditoria.objects.filter(modelo="Carteirinha", objeto_id=str(criada.pk))
    assert registros.exists()
    assert "CARTEIRINHA-SIGILOSA" not in str(list(registros.values()))
