"""Health plans and patients' cards (decision 094). Fictitious data only."""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import ClinicaDiferente, usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modules import configurar
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_convenios", clinica_a, Papel.ADMIN))


@pytest.fixture
def patient(clinica_a):
    with usar_clinica(clinica_a):
        return Patient.objects.create(name="Paciente fictícia do convênio")


@pytest.fixture
def convenio(clinica_a):
    with usar_clinica(clinica_a):
        return HealthPlan.objects.create(name="Saúde Exemplo", registration="000001")


def carteirinha(convenio, **extra):
    return {"convenio": convenio.pk, "plano": "Básico", "number": "123", "active": "on", **extra}


def test_cadastro_do_convenio(clinica_a, admin):
    resposta = admin.post(
        reverse("health_plans:new"),
        {"name": " Plano Fictício ", "registration": "00.000-2", "phone": "", "active": "on"},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        criado = HealthPlan.objects.get()
    assert (criado.name, criado.registration) == ("Plano Fictício", "000002")
    assert "Plano Fictício" in admin.get(reverse("health_plans:list")).content.decode()


@pytest.mark.parametrize(
    ("dados", "campo"),
    [
        ({"name": "saúde exemplo"}, "name"),
        ({"name": "Outro", "registration": "123"}, "registration"),
        ({"name": "Outro", "phone": "99"}, "phone"),
    ],
)
def test_validacoes_do_convenio(dados, campo, convenio, admin):
    resposta = admin.post(reverse("health_plans:new"), dados)
    assert campo in resposta.context["form"].errors


def test_carteirinha_na_ficha_com_validade(clinica_a, patient, convenio, admin):
    url = reverse("health_plans:card_new", args=[patient.pk])
    vencida = (HOJE - datetime.timedelta(days=1)).isoformat()
    resposta = admin.post(url, carteirinha(convenio, number=" 0099 ", valid_until=vencida))
    assert resposta.url == reverse("patients:record", args=[patient.pk])
    with usar_clinica(clinica_a):
        criada = MemberCard.objects.get()
    assert (criada.patient, criada.number, criada.vencida) == (patient, "0099", True)
    ficha = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Saúde Exemplo" in ficha and "Vencida" in ficha
    # The same card number cannot belong to two patients of the same plan.
    with usar_clinica(clinica_a):
        outro = Patient.objects.create(name="Outra paciente fictícia")
    repetida = admin.post(
        reverse("health_plans:card_new", args=[outro.pk]), carteirinha(convenio, number="0099")
    )
    assert "number" in repetida.context["form"].errors
    editar = admin.post(
        reverse("health_plans:card_edit", args=[criada.pk]),
        carteirinha(convenio, number="0099", plano="Apartamento"),
    )
    assert editar.status_code == 302


def test_paciente_sem_carteirinha_e_particular(patient, admin):
    ficha = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Particular" in ficha


def test_convenio_inativo_some_da_carteirinha_nova_mas_fica_na_existente(
    clinica_a, patient, convenio, admin
):
    with usar_clinica(clinica_a):
        existente = MemberCard.objects.create(patient=patient, convenio=convenio, number="1")
        convenio.active = False
        convenio.save()
    nova = admin.get(reverse("health_plans:card_new", args=[patient.pk])).context["form"]
    antiga = admin.get(reverse("health_plans:card_edit", args=[existente.pk])).context["form"]
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
    papel, ver, criar, clinica_a, patient, convenio, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("papel_convenios", clinica_a, papel))
    assert cliente.get(reverse("health_plans:list")).status_code == ver
    assert cliente.get(reverse("health_plans:card_new", args=[patient.pk])).status_code == (criar)


def test_modulo_desligado(clinica_a, patient, convenio, admin):
    assert reverse("health_plans:list") in admin.get(reverse("home")).content.decode()
    configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.CONVENIOS})
    assert admin.get(reverse("health_plans:list")).status_code == 403
    assert reverse("health_plans:list") not in admin.get(reverse("home")).content.decode()
    ficha = admin.get(reverse("patients:record", args=[patient.pk]))
    assert ficha.context.get("carteirinhas") is None


def test_carteirinha_nao_liga_paciente_e_convenio_de_clinicas_diferentes(
    clinica_a, clinica_b, convenio
):
    with usar_clinica(clinica_b):
        de_outra = Patient.objects.create(name="Paciente fictício B")
    with usar_clinica(clinica_b), pytest.raises(ClinicaDiferente):
        MemberCard.objects.create(patient=de_outra, convenio=convenio, number="9")


def test_exclusao_lgpd_apaga_as_carteirinhas(clinica_a, patient, convenio, admin):
    with usar_clinica(clinica_a):
        criada = MemberCard.objects.create(
            patient=patient, convenio=convenio, number="CARTEIRINHA-SIGILOSA"
        )
        patient.archived = True
        patient.save()
    resposta = admin.post(reverse("patients:delete", args=[patient.pk]))
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert not MemberCard.objects.exists()
        assert HealthPlan.objects.filter(pk=convenio.pk).exists()
    registros = AuditEntry.objects.filter(modelo="Carteirinha", objeto_id=str(criada.pk))
    assert registros.exists()
    assert "CARTEIRINHA-SIGILOSA" not in str(list(registros.values()))
