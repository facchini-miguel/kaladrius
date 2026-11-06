"""Related people of a patient: relatives and contacts (decision 101). Fictitious data only."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.audit.record import model_label
from apps.core.isolation import WrongClinic, use_clinic, without_isolation
from apps.core.models import Role
from apps.patients.models import Patient, RelatedPerson

pytestmark = pytest.mark.django_db

MOTHER = RelatedPerson.Relationship.MOTHER


@pytest.fixture
def reception(clinic_a, create_user, client_for):
    return client_for(create_user("recepcao_relacionados", clinic_a, Role.FRONT_DESK))


@pytest.fixture
def family(clinic_a):
    with use_clinic(clinic_a):
        daughter = Patient.objects.create(name="Ana Fictícia")
        mother = Patient.objects.create(name="Rosa Fictícia", whatsapp="54999990001")
        return daughter, mother


def test_link_to_another_patient_shows_on_both_records(clinic_a, family, reception):
    daughter, mother = family
    response = reception.post(
        reverse("patients:related_new", args=[daughter.pk]),
        {"relationship": MOTHER, "other_patient": mother.pk, "name": "", "phone": "", "note": ""},
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        membership = RelatedPerson.objects.get()
    assert membership.display_phone == "54999990001"  # the other patient's own phone
    daughter_record = reception.get(reverse("patients:record", args=[daughter.pk])).content.decode()
    assert "Mãe:" in daughter_record and "Rosa Fictícia" in daughter_record
    mother_record = reception.get(reverse("patients:record", args=[mother.pk])).content.decode()
    assert "Mãe de" in mother_record and "Ana Fictícia" in mother_record


def test_outside_contact_with_phone(clinic_a, family, reception):
    daughter, _ = family
    url = reverse("patients:related_new", args=[daughter.pk])
    data = {
        "relationship": RelatedPerson.Relationship.EMERGENCY,
        "other_patient": "",
        "name": "Contato Inventado",
        "phone": "(54) 99999-0002",
        "note": "Vizinha",
    }
    assert reception.post(url, data).status_code == 302
    with use_clinic(clinic_a):
        contact = RelatedPerson.objects.get()
    assert (contact.phone, contact.display_name) == ("54999990002", "Contato Inventado")
    printed_one = reception.get(reverse("patients:print", args=[daughter.pk])).content.decode()
    assert "Contato Inventado" in printed_one and "Contato de emergência" in printed_one
    # Editing and removing.
    edit_patient = reverse("patients:related_edit", args=[contact.pk])
    assert reception.post(edit_patient, {**data, "note": "Tia"}).status_code == 302
    contact.refresh_from_db()
    assert contact.note == "Tia"
    assert reception.get(reverse("patients:related_remove", args=[contact.pk])).status_code == 302
    remove_ = reception.post(reverse("patients:related_remove", args=[contact.pk]))
    assert remove_.status_code == 302
    assert not RelatedPerson.all_objects.exists()


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": "", "other_patient": ""}, "name"),
        ({"name": "Alguém", "other_patient": "MAE"}, "name"),
        ({"name": "Alguém", "phone": "123"}, "phone"),
        ({"name": "", "other_patient": "PROPRIO"}, "other_patient"),
    ],
)
def test_validations(data, field, family, reception):
    daughter, mother = family
    exchanges = {"MAE": mother.pk, "PROPRIO": daughter.pk}
    data = {k: exchanges.get(v, v) for k, v in data.items()}
    response = reception.post(
        reverse("patients:related_new", args=[daughter.pk]), {"relationship": MOTHER, **data}
    )
    assert field in response.context["form"].errors


def test_duplicate_link(clinic_a, family, reception):
    daughter, mother = family
    with use_clinic(clinic_a):
        RelatedPerson.objects.create(patient=daughter, other_patient=mother, relationship=MOTHER)
    response = reception.post(
        reverse("patients:related_new", args=[daughter.pk]),
        {"relationship": MOTHER, "other_patient": mother.pk},
    )
    assert "other_patient" in response.context["form"].errors


def test_database_requires_patient_or_name(clinic_a, family):
    daughter, _ = family
    with use_clinic(clinic_a), pytest.raises(IntegrityError), transaction.atomic():
        RelatedPerson.objects.create(patient=daughter, relationship=MOTHER)


def test_does_not_link_patients_of_different_clinics(clinic_a, clinic_b, family):
    daughter, _ = family
    with use_clinic(clinic_b):
        other_one = Patient.objects.create(name="De outra clínica")
    with without_isolation(), pytest.raises(WrongClinic):
        RelatedPerson(patient=daughter, other_patient=other_one, relationship=MOTHER).save()


def test_another_clinic_neither_sees_nor_changes(
    clinic_a, clinic_b, family, create_user, client_for
):
    daughter, _ = family
    with use_clinic(clinic_a):
        contact = RelatedPerson.objects.create(
            patient=daughter, relationship=MOTHER, name="Fictícia"
        )
    intruder = client_for(create_user("recepcao_b_rel", clinic_b, Role.FRONT_DESK))
    assert intruder.get(reverse("patients:related_edit", args=[contact.pk])).status_code == 404
    assert intruder.get(reverse("patients:related_new", args=[daughter.pk])).status_code == 404


def test_finance_only_views(clinic_a, family, create_user, client_for):
    daughter, _ = family
    finance_user = client_for(create_user("fin_rel", clinic_a, Role.FINANCE))
    patient_record = finance_user.get(
        reverse("patients:record", args=[daughter.pk])
    ).content.decode()
    assert "Pessoas relacionadas" in patient_record
    assert reverse("patients:related_new", args=[daughter.pk]) not in patient_record
    new_patient = finance_user.get(reverse("patients:related_new", args=[daughter.pk]))
    assert new_patient.status_code == 403


def test_lgpd_deletion_deletes_links_on_both_sides(clinic_a, family, create_user, client_for):
    daughter, mother = family
    with use_clinic(clinic_a):
        of_daughter = RelatedPerson.objects.create(
            patient=daughter,
            relationship=RelatedPerson.Relationship.EMERGENCY,
            name="NOME-SIGILOSO",
        )
        RelatedPerson.objects.create(patient=mother, other_patient=daughter, relationship=MOTHER)
        daughter.archived = True
        daughter.save()
    admin = client_for(create_user("admin_rel", clinic_a, Role.ADMIN))
    assert admin.post(reverse("patients:delete", args=[daughter.pk])).status_code == 302
    assert not RelatedPerson.all_objects.exists()
    records = AuditEntry.objects.filter(
        model_name=model_label(RelatedPerson), object_id=str(of_daughter.pk)
    )
    assert records.exists()
    assert "NOME-SIGILOSO" not in str(list(records.values()))
