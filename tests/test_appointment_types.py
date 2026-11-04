import pytest
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import Clinic, Papel
from apps.dentistry.teeth import TIPOS_DE_ATENDIMENTO
from apps.schedule.models import TIPOS_PADRAO, AppointmentType

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("area", "esperados"),
    [
        (Clinic.Area.ODONTOLOGIA, TIPOS_DE_ATENDIMENTO),
        (Clinic.Area.MEDICINA, TIPOS_PADRAO),
        (Clinic.Area.OUTRA, TIPOS_PADRAO),
    ],
)
def test_clinica_nova_recebe_os_tipos_da_sua_area(area, esperados):
    # Decision 080: dental types for the Odontologia area, general ones for the others.
    clinic = Clinic.objects.create(name="Nova", area=area)
    with usar_clinica(clinic):
        tipos = {t.name: t.cor for t in AppointmentType.objects.all()}
    assert tipos == dict(esperados)


def test_tipos_sao_isolados_por_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    with usar_clinica(clinica_b):
        AppointmentType.objects.create(name="Exclusivo da B", cor="#000000")
        de_b = AppointmentType.objects.get(name="Cirurgia")
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    conteudo = cliente.get(reverse("schedule:types")).content.decode()
    assert "Cirurgia" in conteudo
    assert "Exclusivo da B" not in conteudo
    assert cliente.get(reverse("schedule:type_edit", args=[de_b.pk])).status_code == 404


def test_admin_cria_e_nome_repetido_e_recusado(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    url = reverse("schedule:type_new")
    assert (
        cliente.post(url, {"name": "Retorno", "cor": "#112233", "active": "on"}).status_code == 302
    )
    resposta = cliente.post(url, {"name": "retorno", "cor": "#112233"})
    assert resposta.status_code == 200
    assert "Já existe um tipo de atendimento com este nome" in resposta.content.decode()


def test_mesmo_nome_e_permitido_em_outra_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Papel.ADMIN))
    resposta = cliente.post(reverse("schedule:type_new"), {"name": "Retorno", "cor": "#112233"})
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        AppointmentType.objects.create(name="Retorno", cor="#445566")


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_recepcao_e_profissional_so_consultam(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    with usar_clinica(clinica_a):
        kind = AppointmentType.objects.first()
    assert cliente.get(reverse("schedule:types")).status_code == 200
    assert cliente.get(reverse("schedule:type_new")).status_code == 403
    assert cliente.post(reverse("schedule:type_delete", args=[kind.pk])).status_code == 403
    conteudo = cliente.get(reverse("schedule:types")).content.decode()
    assert "Novo tipo" not in conteudo


def test_menu_cadastros(clinica_a, criar_usuario, cliente_de):
    conteudo = (
        cliente_de(criar_usuario("recepcao", clinica_a)).get(reverse("home")).content.decode()
    )
    for item in ["Cadastros", "Profissionais", "Tipos de atendimento", "Cidades", "Bancos"]:
        assert item in conteudo
