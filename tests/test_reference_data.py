import pytest
from django.urls import reverse

from apps.core.models import Role
from apps.reference_data.models import Bank, City, MaritalStatus, State

pytestmark = pytest.mark.django_db


def test_official_data_loaded_by_migration():
    assert State.objects.count() == 27
    assert City.objects.count() > 5500
    assert Bank.objects.filter(code=1).get().short_name == "BCO DO BRASIL S.A."
    assert MaritalStatus.objects.count() == 6
    assert City.objects.get(code=4205407).name == "Florianópolis"
    assert City.objects.get(code=4205407).state.abbreviation == "SC"


def test_city_list_filters_by_state_and_ignores_accents(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK))
    response = cliente.get(reverse("reference_data:cities"), {"state": 42, "q": "florianopolis"})
    content = response.content.decode()
    assert response.status_code == 200
    assert "Florianópolis" in content
    assert "1 cidade" in content


def test_bank_list_searches_by_code(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK))
    content = cliente.get(reverse("reference_data:banks"), {"q": "341"}).content.decode()
    assert "ITAÚ" in content.upper()


def test_pagination_keeps_filters(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK))
    content = cliente.get(reverse("reference_data:cities"), {"state": 31}).content.decode()  # MG
    assert "state=31&amp;q=&amp;page=2" in content


def test_city_options_for_chained_select(client, criar_usuario):
    url = reverse("reference_data:city_options")
    assert client.get(url, {"state": 42}).status_code == 302  # login required
    client.force_login(criar_usuario("qualquer"))
    content = client.get(url, {"state": 42}).content.decode()
    assert '<option value="4205407">Florianópolis</option>' in content
    assert "São Paulo" not in content
    assert client.get(url, {"state": "x"}).content.decode().count("<option") == 1


def test_reference_tables_require_clinic(criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("solto"))
    assert cliente.get(reverse("reference_data:cities")).status_code == 403
