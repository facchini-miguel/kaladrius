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

TODAY = timezone.localdate()


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_convenios", clinic_a, Role.ADMIN))


@pytest.fixture
def patient(clinic_a):
    with use_clinic(clinic_a):
        return Patient.objects.create(name="Paciente fictícia do convênio")


@pytest.fixture
def health_plan(clinic_a):
    with use_clinic(clinic_a):
        return HealthPlan.objects.create(name="Saúde Exemplo", registration="000001")


def plan_card(health_plan, **extra):
    return {
        "health_plan": health_plan.pk,
        "plan": "Básico",
        "number": "123",
        "active": "on",
        **extra,
    }


def test_health_plan_registration(clinic_a, admin):
    response = admin.post(
        reverse("health_plans:new"),
        {"name": " Plano Fictício ", "registration": "00.000-2", "phone": "", "active": "on"},
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        created = HealthPlan.objects.get()
    assert (created.name, created.registration) == ("Plano Fictício", "000002")
    assert "Plano Fictício" in admin.get(reverse("health_plans:list")).content.decode()


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": "saúde exemplo"}, "name"),
        ({"name": "Outro", "registration": "123"}, "registration"),
        ({"name": "Outro", "phone": "99"}, "phone"),
    ],
)
def test_health_plan_validations(data, field, health_plan, admin):
    response = admin.post(reverse("health_plans:new"), data)
    assert field in response.context["form"].errors


def test_member_card_on_record_with_expiry(clinic_a, patient, health_plan, admin):
    url = reverse("health_plans:card_new", args=[patient.pk])
    is_expired = (TODAY - datetime.timedelta(days=1)).isoformat()
    response = admin.post(url, plan_card(health_plan, number=" 0099 ", valid_until=is_expired))
    assert response.url == reverse("patients:record", args=[patient.pk])
    with use_clinic(clinic_a):
        created_one = MemberCard.objects.get()
    assert (created_one.patient, created_one.number, created_one.is_expired) == (
        patient,
        "0099",
        True,
    )
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Saúde Exemplo" in patient_record and "Vencida" in patient_record
    # The same card number cannot belong to two patients of the same plan.
    with use_clinic(clinic_a):
        other = Patient.objects.create(name="Outra paciente fictícia")
    repeated = admin.post(
        reverse("health_plans:card_new", args=[other.pk]), plan_card(health_plan, number="0099")
    )
    assert "number" in repeated.context["form"].errors
    edit_health_plan = admin.post(
        reverse("health_plans:card_edit", args=[created_one.pk]),
        plan_card(health_plan, number="0099", plan="Apartamento"),
    )
    assert edit_health_plan.status_code == 302


def test_patient_without_card_is_private(patient, admin):
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Particular" in patient_record


def test_inactive_plan_hidden_from_new_card_but_kept_on_existing(
    clinic_a, patient, health_plan, admin
):
    with use_clinic(clinic_a):
        existing = MemberCard.objects.create(patient=patient, health_plan=health_plan, number="1")
        health_plan.active = False
        health_plan.save()
    new_one = admin.get(reverse("health_plans:card_new", args=[patient.pk])).context["form"]
    old_one = admin.get(reverse("health_plans:card_edit", args=[existing.pk])).context["form"]
    with use_clinic(clinic_a):
        assert health_plan not in new_one.fields["health_plan"].queryset
        assert health_plan in old_one.fields["health_plan"].queryset


@pytest.mark.parametrize(
    ("role", "view_", "create"),
    [
        (Role.FRONT_DESK, 200, 200),
        (Role.PRACTITIONER, 200, 403),
        (Role.FINANCE, 200, 403),
    ],
)
def test_permissions_by_role(
    role, view_, create, clinic_a, patient, health_plan, create_user, client_for
):
    user_client = client_for(create_user("papel_convenios", clinic_a, role))
    assert user_client.get(reverse("health_plans:list")).status_code == view_
    assert user_client.get(reverse("health_plans:card_new", args=[patient.pk])).status_code == (
        create
    )


def test_module_off(clinic_a, patient, health_plan, admin):
    assert reverse("health_plans:list") in admin.get(reverse("home")).content.decode()
    configure(clinic_a, GENERAL_MODULES - {ModuleCode.HEALTH_PLANS})
    assert admin.get(reverse("health_plans:list")).status_code == 403
    assert reverse("health_plans:list") not in admin.get(reverse("home")).content.decode()
    patient_record = admin.get(reverse("patients:record", args=[patient.pk]))
    assert patient_record.context.get("plan_cards") is None


def test_card_does_not_link_patient_and_plan_of_different_clinics(clinic_a, clinic_b, health_plan):
    with use_clinic(clinic_b):
        of_other = Patient.objects.create(name="Paciente fictício B")
    with use_clinic(clinic_b), pytest.raises(WrongClinic):
        MemberCard.objects.create(patient=of_other, health_plan=health_plan, number="9")


def test_lgpd_deletion_deletes_the_cards(clinic_a, patient, health_plan, admin):
    with use_clinic(clinic_a):
        created_one = MemberCard.objects.create(
            patient=patient, health_plan=health_plan, number="CARTEIRINHA-SIGILOSA"
        )
        patient.archived = True
        patient.save()
    response = admin.post(reverse("patients:delete", args=[patient.pk]))
    assert response.status_code == 302
    with use_clinic(clinic_a):
        assert not MemberCard.objects.exists()
        assert HealthPlan.objects.filter(pk=health_plan.pk).exists()
    records = AuditEntry.objects.filter(model_name="Carteirinha", object_id=str(created_one.pk))
    assert records.exists()
    assert "CARTEIRINHA-SIGILOSA" not in str(list(records.values()))
