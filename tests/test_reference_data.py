import pytest
from django.urls import reverse

from apps.core.models import Papel
from apps.reference_data.models import Bank, City, MaritalStatus, State

pytestmark = pytest.mark.django_db


def test_dados_oficiais_carregados_pela_migracao():
    assert State.objects.count() == 27
    assert City.objects.count() > 5500
    assert Bank.objects.filter(code=1).get().nome_curto == "BCO DO BRASIL S.A."
    assert MaritalStatus.objects.count() == 6
    assert City.objects.get(code=4205407).name == "Florianópolis"
    assert City.objects.get(code=4205407).state.sigla == "SC"


def test_lista_de_cidades_filtra_por_uf_e_ignora_acentos(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    resposta = cliente.get(reverse("reference_data:cities"), {"state": 42, "q": "florianopolis"})
    content = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Florianópolis" in content
    assert "1 cidade" in content


def test_lista_de_bancos_busca_por_codigo(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    content = cliente.get(reverse("reference_data:banks"), {"q": "341"}).content.decode()
    assert "ITAÚ" in content.upper()


def test_paginacao_preserva_os_filtros(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    content = cliente.get(reverse("reference_data:cities"), {"state": 31}).content.decode()  # MG
    assert "state=31&amp;q=&amp;pagina=2" in content


def test_opcoes_de_cidades_para_o_select_encadeado(client, criar_usuario):
    url = reverse("reference_data:city_options")
    assert client.get(url, {"state": 42}).status_code == 302  # login required
    client.force_login(criar_usuario("qualquer"))
    content = client.get(url, {"state": 42}).content.decode()
    assert '<option value="4205407">Florianópolis</option>' in content
    assert "São Paulo" not in content
    assert client.get(url, {"state": "x"}).content.decode().count("<option") == 1


def test_tabelas_de_referencia_exigem_clinica(criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("solto"))
    assert cliente.get(reverse("reference_data:cities")).status_code == 403
