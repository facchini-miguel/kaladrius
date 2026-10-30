"""Neighborhoods and streets as suggestions on the patient form (decision 100)."""

import pytest
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente
from apps.referencias.models import Bairro, Logradouro

pytestmark = pytest.mark.django_db

CARLOS_BARBOSA = 4304804
URL = reverse("referencias:sugestoes_endereco")


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_enderecos", clinica_a, Papel.RECEPCAO))


def test_bairros_e_logradouros_do_odonto_carregados():
    # 75 in the legacy, 5 of them registered twice in the same city.
    assert Bairro.objects.count() == 70
    assert Bairro.objects.filter(cidade_id=CARLOS_BARBOSA).count() == 39
    assert Logradouro.objects.count() == 316
    assert Logradouro.objects.filter(nome__startswith="Rua ").exists()


def test_sugestoes_da_cidade_mais_as_ja_digitadas_pela_clinica(clinica_a, clinica_b, recepcao):
    with usar_clinica(clinica_a):
        Paciente.objects.create(
            nome="Paciente fictício A",
            cidade_id=CARLOS_BARBOSA,
            bairro="Bairro Novo Fictício",
            logradouro="Rua Inventada A",
        )
    with usar_clinica(clinica_b):
        Paciente.objects.create(
            nome="Paciente fictício B", cidade_id=CARLOS_BARBOSA, bairro="Bairro de Outra Clínica"
        )
    texto = recepcao.get(URL, {"cidade": CARLOS_BARBOSA}).content.decode()
    assert 'id="bairros-sugeridos"' in texto and 'value="Centro"' in texto
    assert 'value="Bairro Novo Fictício"' in texto and 'value="Rua Inventada A"' in texto
    assert "Outra Clínica" not in texto  # another clinic's patients stay private


def test_cidade_sem_dados_e_parametro_invalido(recepcao):
    assert "<option" not in recepcao.get(URL, {"cidade": "3550308"}).content.decode()
    assert recepcao.get(URL, {"cidade": "abc"}).status_code == 200


def test_formulario_do_paciente_liga_as_sugestoes(recepcao):
    pagina = recepcao.get(reverse("pacientes:novo")).content.decode()
    assert 'list="bairros-sugeridos"' in pagina and 'list="logradouros-sugeridos"' in pagina
    assert reverse("referencias:sugestoes_endereco") in pagina


def test_sem_login_nao_ve_sugestoes(client):
    assert client.get(URL, {"cidade": CARLOS_BARBOSA}).status_code == 302
