"""Neighborhoods and streets as suggestions on the patient form (decision 100)."""

import pytest
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.patients.models import Patient
from apps.reference_data.models import Neighborhood, Street

pytestmark = pytest.mark.django_db

CARLOS_BARBOSA = 4304804
URL = reverse("reference_data:address_suggestions")


@pytest.fixture
def reception(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_enderecos", clinica_a, Papel.RECEPCAO))


def test_bairros_e_logradouros_do_odonto_carregados():
    # 75 in the legacy, 5 of them registered twice in the same city.
    assert Neighborhood.objects.count() == 70
    assert Neighborhood.objects.filter(city_id=CARLOS_BARBOSA).count() == 39
    assert Street.objects.count() == 316
    assert Street.objects.filter(name__startswith="Rua ").exists()


def test_sugestoes_da_cidade_mais_as_ja_digitadas_pela_clinica(clinica_a, clinica_b, reception):
    with usar_clinica(clinica_a):
        Patient.objects.create(
            name="Paciente fictício A",
            city_id=CARLOS_BARBOSA,
            neighborhood="Bairro Novo Fictício",
            street="Rua Inventada A",
        )
    with usar_clinica(clinica_b):
        Patient.objects.create(
            name="Paciente fictício B",
            city_id=CARLOS_BARBOSA,
            neighborhood="Bairro de Outra Clínica",
        )
    text = reception.get(URL, {"city": CARLOS_BARBOSA}).content.decode()
    assert 'id="bairros-sugeridos"' in text and 'value="Centro"' in text
    assert 'value="Bairro Novo Fictício"' in text and 'value="Rua Inventada A"' in text
    assert "Outra Clínica" not in text  # another clinic's patients stay private


def test_cidade_sem_dados_e_parametro_invalido(reception):
    assert "<option" not in reception.get(URL, {"city": "3550308"}).content.decode()
    assert reception.get(URL, {"city": "abc"}).status_code == 200


def test_formulario_do_paciente_liga_as_sugestoes(reception):
    page = reception.get(reverse("patients:new")).content.decode()
    assert 'list="bairros-sugeridos"' in page and 'list="logradouros-sugeridos"' in page
    assert reverse("reference_data:address_suggestions") in page


def test_sem_login_nao_ve_sugestoes(client):
    assert client.get(URL, {"city": CARLOS_BARBOSA}).status_code == 302
