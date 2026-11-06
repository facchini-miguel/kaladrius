"""Neighborhoods and streets as suggestions on the patient form (decision 100)."""

import re

import pytest
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.patients.models import Patient
from apps.reference_data.models import Neighborhood, Street

pytestmark = pytest.mark.django_db

CARLOS_BARBOSA = 4304804
URL = reverse("reference_data:address_suggestions")


@pytest.fixture
def reception(clinic_a, create_user, client_for):
    return client_for(create_user("recepcao_enderecos", clinic_a, Role.FRONT_DESK))


def test_odonto_neighborhoods_and_streets_loaded():
    # 75 in the legacy, 5 of them registered twice in the same city.
    assert Neighborhood.objects.count() == 70
    assert Neighborhood.objects.filter(city_id=CARLOS_BARBOSA).count() == 39
    assert Street.objects.count() == 316
    assert Street.objects.filter(name__startswith="Rua ").exists()


def test_city_suggestions_plus_those_typed_by_the_clinic(clinic_a, clinic_b, reception):
    with use_clinic(clinic_a):
        Patient.objects.create(
            name="Paciente fictício A",
            city_id=CARLOS_BARBOSA,
            neighborhood="Bairro Novo Fictício",
            street="Rua Inventada A",
        )
    with use_clinic(clinic_b):
        Patient.objects.create(
            name="Paciente fictício B",
            city_id=CARLOS_BARBOSA,
            neighborhood="Bairro de Outra Clínica",
        )
    text = reception.get(URL, {"city": CARLOS_BARBOSA}).content.decode()
    assert 'id="suggested-neighborhoods"' in text and 'value="Centro"' in text
    assert 'value="Bairro Novo Fictício"' in text and 'value="Rua Inventada A"' in text
    assert "Outra Clínica" not in text  # another clinic's patients stay private


def test_city_without_data_and_invalid_parameter(reception):
    assert "<option" not in reception.get(URL, {"city": "3550308"}).content.decode()
    assert reception.get(URL, {"city": "abc"}).status_code == 200


def test_patient_form_wires_the_suggestions(reception):
    page = reception.get(reverse("patients:new")).content.decode()
    assert 'list="suggested-neighborhoods"' in page and 'list="suggested-streets"' in page
    assert reverse("reference_data:address_suggestions") in page


def test_patient_form_htmx_targets_exist(reception):
    """Each HTMX target of the form is on the page: after the field renames the state still
    pointed at #id_cidade, so choosing a state no longer loaded its cities."""
    page = reception.get(reverse("patients:new")).content.decode()
    targets = re.findall(r'hx-target="#([\w-]+)"', page)
    assert "id_city" in targets
    for target in targets:
        assert f'id="{target}"' in page, target


def test_no_suggestions_without_login(client):
    assert client.get(URL, {"city": CARLOS_BARBOSA}).status_code == 302
