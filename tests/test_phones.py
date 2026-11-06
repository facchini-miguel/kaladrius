"""Phones with a valid area code and the ninth mobile digit, so WhatsApp links work
(owner: "coloque o DDD, porque o whats não funciona se não tiver certo")."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from faker import Faker

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.core.templatetags.formats import whatsapp
from apps.core.validators import ninth_digit, normalize_phone
from apps.legacy.anonymization import _same_length
from apps.patients.models import Patient


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("(54) 99123-4567", "54991234567"),
        ("54 9123-4567", "54991234567"),  # old 8-digit mobile gets the ninth digit
        ("(54) 3461-3354", "5434613354"),  # landline stays with 8 digits
        ("054 3461-3354", "5434613354"),  # carrier prefix 0
        ("+55 54 99123-4567", "54991234567"),  # country code
        ("", ""),
    ],
)
def test_normalize_phone(typed, expected):
    assert normalize_phone(typed) == expected


@pytest.mark.parametrize("typed", ["(20) 3461-3354", "(54) 3123-45678", "123", "5491234"])
def test_invalid_phone(typed):
    with pytest.raises(ValidationError):
        normalize_phone(typed)


def test_ninth_digit_only_on_mobile():
    assert ninth_digit("5481234567") == "54981234567"
    assert ninth_digit("5434613354") == "5434613354"
    assert ninth_digit("99998888") == "99998888"  # no area code: left as it was


def test_whatsapp_link_with_area_code_and_ninth_digit():
    assert whatsapp("54991234567") == "https://wa.me/5554991234567"


@pytest.mark.django_db
def test_patient_registration_fixes_the_mobile(clinic_a, create_user, client_for):
    user_client = client_for(create_user("recepcao_fones", clinic_a, Role.FRONT_DESK))
    response = user_client.post(
        reverse("patients:new"),
        {
            "kind": "PF",
            "name": "Paciente Fictício",
            "mobile_phone": "(54) 8123-4567",
            "whatsapp": "54 8123-4567",
            "home_phone": "(54) 3461-3354",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        patient = Patient.objects.get()
    assert (patient.mobile_phone, patient.whatsapp, patient.home_phone) == (
        "54981234567",
        "54981234567",
        "5434613354",
    )
    wrong = user_client.post(
        reverse("patients:new"), {"kind": "PF", "name": "Outro", "whatsapp": "(20) 98123-4567"}
    )
    assert "whatsapp" in wrong.context["form"].errors


def test_anonymization_keeps_valid_mobile_and_landline():
    fake = Faker("pt_BR")
    for _ in range(50):
        mobile = _same_length("5484123456", fake)  # old mobile without the ninth digit
        fixed_value = _same_length("5434613354", fake)
        assert len(mobile) == 11 and mobile.startswith("549")
        assert len(fixed_value) == 10 and fixed_value.startswith("54") and fixed_value[2] in "2345"
