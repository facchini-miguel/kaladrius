"""Health plans and patients' cards (decision 094). Fictitious data only."""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import WrongClinic, use_clinic
from apps.core.models import GENERAL_MODULES, ModuleCode, Role
from apps.core.modules import configure
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_convenios", clinica_a, Role.ADMIN))


@pytest.fixture
def patient(clinica_a):
    with use_clinic(clinica_a):
        return Patient.objects.create(name="Paciente fictícia do convênio")


@pytest.fixture
def health_plan(clinica_a):
    with use_clinic(clinica_a):
        return HealthPlan.objects.create(name="Saúde Exemplo", registration="000001")


def carteirinha(health_plan, **extra):
    return {
        "health_plan": health_plan.pk,
        "plan": "Básico",
        "number": "123",
        "active": "on",
        **extra,
    }


def test_cadastro_do_convenio(clinica_a, admin):
    response = admin.post(
        reverse("health_plans:new"),
        {"name": " Plano Fictício ", "registration": "00.000-2", "phone": "", "active": "on"},
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        criado = HealthPlan.objects.get()
    assert (criado.name, criado.registration) == ("Plano Fictício", "000002")
    assert "Plano Fictício" in admin.get(reverse("health_plans:list")).content.decode()


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": "saúde exemplo"}, "name"),
        ({"name": "Outro", "registration": "123"}, "registration"),
        ({"name": "Outro", "phone": "99"}, "phone"),
    ],
)
def test_validacoes_do_convenio(data, field, health_plan, admin):
    response = admin.post(reverse("health_plans:new"), data)
    assert field in response.context["form"].errors


def test_carteirinha_na_ficha_com_validade(clinica_a, patient, health_plan, admin):
    url = reverse("health_plans:card_new", args=[patient.pk])
    is_expired = (HOJE - datetime.timedelta(days=1)).isoformat()
    response = admin.post(url, carteirinha(health_plan, number=" 0099 ", valid_until=is_expired))
    assert response.url == reverse("patients:record", args=[patient.pk])
    with use_clinic(clinica_a):
        criada = MemberCard.objects.get()
    assert (criada.patient, criada.number, criada.is_expired) == (patient, "0099", True)
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Saúde Exemplo" in patient_record and "Vencida" in patient_record
    # The same card number cannot belong to two patients of the same plan.
    with use_clinic(clinica_a):
        other = Patient.objects.create(name="Outra paciente fictícia")
    repetida = admin.post(
        reverse("health_plans:card_new", args=[other.pk]), carteirinha(health_plan, number="0099")
    )
    assert "number" in repetida.context["form"].errors
    edit_health_plan = admin.post(
        reverse("health_plans:card_edit", args=[criada.pk]),
        carteirinha(health_plan, number="0099", plan="Apartamento"),
    )
    assert edit_health_plan.status_code == 302


def test_paciente_sem_carteirinha_e_particular(patient, admin):
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Particular" in patient_record


def test_convenio_inativo_some_da_carteirinha_nova_mas_fica_na_existente(
    clinica_a, patient, health_plan, admin
):
    with use_clinic(clinica_a):
        existente = MemberCard.objects.create(patient=patient, health_plan=health_plan, number="1")
        health_plan.active = False
        health_plan.save()
    nova = admin.get(reverse("health_plans:card_new", args=[patient.pk])).context["form"]
    antiga = admin.get(reverse("health_plans:card_edit", args=[existente.pk])).context["form"]
    with use_clinic(clinica_a):
        assert health_plan not in nova.fields["health_plan"].queryset
        assert health_plan in antiga.fields["health_plan"].queryset


@pytest.mark.parametrize(
    ("role", "ver", "criar"),
    [
        (Role.FRONT_DESK, 200, 200),
        (Role.PRACTITIONER, 200, 403),
        (Role.FINANCE, 200, 403),
    ],
)
def test_permissoes_por_papel(
    role, ver, criar, clinica_a, patient, health_plan, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("papel_convenios", clinica_a, role))
    assert cliente.get(reverse("health_plans:list")).status_code == ver
    assert cliente.get(reverse("health_plans:card_new", args=[patient.pk])).status_code == (criar)


def test_modulo_desligado(clinica_a, patient, health_plan, admin):
    assert reverse("health_plans:list") in admin.get(reverse("home")).content.decode()
    configure(clinica_a, GENERAL_MODULES - {ModuleCode.HEALTH_PLANS})
    assert admin.get(reverse("health_plans:list")).status_code == 403
    assert reverse("health_plans:list") not in admin.get(reverse("home")).content.decode()
    patient_record = admin.get(reverse("patients:record", args=[patient.pk]))
    assert patient_record.context.get("carteirinhas") is None


def test_carteirinha_nao_liga_paciente_e_convenio_de_clinicas_diferentes(
    clinica_a, clinica_b, health_plan
):
    with use_clinic(clinica_b):
        de_outra = Patient.objects.create(name="Paciente fictício B")
    with use_clinic(clinica_b), pytest.raises(WrongClinic):
        MemberCard.objects.create(patient=de_outra, health_plan=health_plan, number="9")


def test_exclusao_lgpd_apaga_as_carteirinhas(clinica_a, patient, health_plan, admin):
    with use_clinic(clinica_a):
        criada = MemberCard.objects.create(
            patient=patient, health_plan=health_plan, number="CARTEIRINHA-SIGILOSA"
        )
        patient.archived = True
        patient.save()
    response = admin.post(reverse("patients:delete", args=[patient.pk]))
    assert response.status_code == 302
    with use_clinic(clinica_a):
        assert not MemberCard.objects.exists()
        assert HealthPlan.objects.filter(pk=health_plan.pk).exists()
    registros = AuditEntry.objects.filter(model_name="Carteirinha", object_id=str(criada.pk))
    assert registros.exists()
    assert "CARTEIRINHA-SIGILOSA" not in str(list(registros.values()))
