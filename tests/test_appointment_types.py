import pytest
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Role
from apps.dentistry.teeth import APPOINTMENT_TYPES
from apps.schedule.models import DEFAULT_TYPES, AppointmentType

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("area", "esperados"),
    [
        (Clinic.Area.DENTISTRY, APPOINTMENT_TYPES),
        (Clinic.Area.MEDICINE, DEFAULT_TYPES),
        (Clinic.Area.OUTRA, DEFAULT_TYPES),
    ],
)
def test_clinica_nova_recebe_os_tipos_da_sua_area(area, esperados):
    # Decision 080: dental types for the Odontologia area, general ones for the others.
    clinic = Clinic.objects.create(name="Nova", area=area)
    with use_clinic(clinic):
        appointment_types = {t.name: t.color for t in AppointmentType.objects.all()}
    assert appointment_types == dict(esperados)


def test_tipos_sao_isolados_por_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    with use_clinic(clinica_b):
        AppointmentType.objects.create(name="Exclusivo da B", color="#000000")
        de_b = AppointmentType.objects.get(name="Cirurgia")
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    content = cliente.get(reverse("schedule:types")).content.decode()
    assert "Cirurgia" in content
    assert "Exclusivo da B" not in content
    assert cliente.get(reverse("schedule:type_edit", args=[de_b.pk])).status_code == 404


def test_admin_cria_e_nome_repetido_e_recusado(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    url = reverse("schedule:type_new")
    assert (
        cliente.post(url, {"name": "Retorno", "color": "#112233", "active": "on"}).status_code
        == 302
    )
    response = cliente.post(url, {"name": "retorno", "color": "#112233"})
    assert response.status_code == 200
    assert "Já existe um tipo de atendimento com este nome" in response.content.decode()


def test_mesmo_nome_e_permitido_em_outra_clinica(clinica_a, clinica_b, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Role.ADMIN))
    response = cliente.post(reverse("schedule:type_new"), {"name": "Retorno", "color": "#112233"})
    assert response.status_code == 302
    with use_clinic(clinica_a):
        AppointmentType.objects.create(name="Retorno", color="#445566")


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_recepcao_e_profissional_so_consultam(role, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, role))
    with use_clinic(clinica_a):
        kind = AppointmentType.objects.first()
    assert cliente.get(reverse("schedule:types")).status_code == 200
    assert cliente.get(reverse("schedule:type_new")).status_code == 403
    assert cliente.post(reverse("schedule:type_delete", args=[kind.pk])).status_code == 403
    content = cliente.get(reverse("schedule:types")).content.decode()
    assert "Novo tipo" not in content


def test_menu_cadastros(clinica_a, criar_usuario, cliente_de):
    content = cliente_de(criar_usuario("recepcao", clinica_a)).get(reverse("home")).content.decode()
    for item in ["Cadastros", "Profissionais", "Tipos de atendimento", "Cidades", "Bancos"]:
        assert item in content
