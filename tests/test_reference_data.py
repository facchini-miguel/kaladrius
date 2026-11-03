import pytest
from django.urls import reverse

from apps.core.models import Papel
from apps.referencias.models import UF, Banco, Cidade, EstadoCivil

pytestmark = pytest.mark.django_db


def test_dados_oficiais_carregados_pela_migracao():
    assert UF.objects.count() == 27
    assert Cidade.objects.count() > 5500
    assert Banco.objects.filter(codigo=1).get().nome_curto == "BCO DO BRASIL S.A."
    assert EstadoCivil.objects.count() == 6
    assert Cidade.objects.get(codigo=4205407).nome == "Florianópolis"
    assert Cidade.objects.get(codigo=4205407).uf.sigla == "SC"


def test_lista_de_cidades_filtra_por_uf_e_ignora_acentos(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    resposta = cliente.get(reverse("referencias:cidades"), {"uf": 42, "q": "florianopolis"})
    conteudo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Florianópolis" in conteudo
    assert "1 cidade" in conteudo


def test_lista_de_bancos_busca_por_codigo(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    conteudo = cliente.get(reverse("referencias:bancos"), {"q": "341"}).content.decode()
    assert "ITAÚ" in conteudo.upper()


def test_paginacao_preserva_os_filtros(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    conteudo = cliente.get(reverse("referencias:cidades"), {"uf": 31}).content.decode()  # MG
    assert "uf=31&amp;q=&amp;pagina=2" in conteudo


def test_opcoes_de_cidades_para_o_select_encadeado(client, criar_usuario):
    url = reverse("referencias:opcoes_cidades")
    assert client.get(url, {"uf": 42}).status_code == 302  # login required
    client.force_login(criar_usuario("qualquer"))
    conteudo = client.get(url, {"uf": 42}).content.decode()
    assert '<option value="4205407">Florianópolis</option>' in conteudo
    assert "São Paulo" not in conteudo
    assert client.get(url, {"uf": "x"}).content.decode().count("<option") == 1


def test_tabelas_de_referencia_exigem_clinica(criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("solto"))
    assert cliente.get(reverse("referencias:cidades")).status_code == 403
