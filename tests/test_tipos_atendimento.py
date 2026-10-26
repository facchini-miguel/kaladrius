import pytest
from django.urls import reverse

from apps.agenda.models import TIPOS_PADRAO, TipoAtendimento
from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica, Papel

pytestmark = pytest.mark.django_db


def test_clinica_nova_recebe_os_tipos_padrao():
    clinica = Clinica.objects.create(nome="Nova")
    with usar_clinica(clinica):
        tipos = {t.nome: t.cor for t in TipoAtendimento.objects.all()}
    assert tipos == dict(TIPOS_PADRAO)
    assert tipos["Cirurgia"] == "#f7a5a5"


def test_tipos_sao_isolados_por_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    with usar_clinica(clinica_b):
        TipoAtendimento.objects.create(nome="Exclusivo da B", cor="#000000")
        de_b = TipoAtendimento.objects.get(nome="Cirurgia")
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    conteudo = cliente.get(reverse("agenda:tipos")).content.decode()
    assert "Cirurgia" in conteudo
    assert "Exclusivo da B" not in conteudo
    assert cliente.get(reverse("agenda:tipo_editar", args=[de_b.pk])).status_code == 404


def test_admin_cria_e_nome_repetido_e_recusado(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    url = reverse("agenda:tipo_novo")
    assert (
        cliente.post(url, {"nome": "Retorno", "cor": "#112233", "ativo": "on"}).status_code == 302
    )
    resposta = cliente.post(url, {"nome": "retorno", "cor": "#112233"})
    assert resposta.status_code == 200
    assert "Já existe um tipo de atendimento com este nome" in resposta.content.decode()


def test_mesmo_nome_e_permitido_em_outra_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    resposta = cliente.post(reverse("agenda:tipo_novo"), {"nome": "Retorno", "cor": "#112233"})
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        TipoAtendimento.objects.create(nome="Retorno", cor="#445566")


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_recepcao_e_profissional_so_consultam(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    with usar_clinica(clinica_a):
        tipo = TipoAtendimento.objects.first()
    assert cliente.get(reverse("agenda:tipos")).status_code == 200
    assert cliente.get(reverse("agenda:tipo_novo")).status_code == 403
    assert cliente.post(reverse("agenda:tipo_excluir", args=[tipo.pk])).status_code == 403
    conteudo = cliente.get(reverse("agenda:tipos")).content.decode()
    assert "Novo tipo" not in conteudo


def test_menu_cadastros(clinica_a, criar_usuario, cliente_de):
    conteudo = (
        cliente_de(criar_usuario("recepcao", clinica_a)).get(reverse("inicio")).content.decode()
    )
    for item in ["Cadastros", "Profissionais", "Tipos de atendimento", "Cidades", "Bancos"]:
        assert item in conteudo
