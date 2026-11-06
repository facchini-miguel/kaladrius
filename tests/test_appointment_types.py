import pytest
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Role
from apps.dentistry.teeth import APPOINTMENT_TYPES
from apps.schedule.models import DEFAULT_TYPES, AppointmentType

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("area", "expected_list"),
    [
        (Clinic.Area.DENTISTRY, APPOINTMENT_TYPES),
        (Clinic.Area.MEDICINE, DEFAULT_TYPES),
        (Clinic.Area.OUTRA, DEFAULT_TYPES),
    ],
)
def test_new_clinic_gets_the_types_of_its_area(area, expected_list):
    # Decision 080: dental types for the Odontologia area, general ones for the others.
    clinic = Clinic.objects.create(name="Nova", area=area)
    with use_clinic(clinic):
        appointment_types = {t.name: t.color for t in AppointmentType.objects.all()}
    assert appointment_types == dict(expected_list)


def test_types_are_isolated_per_clinic(clinic_a, clinic_b, create_user, client_for):
    with use_clinic(clinic_b):
        AppointmentType.objects.create(name="Exclusivo da B", color="#000000")
        of_b = AppointmentType.objects.get(name="Cirurgia")
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    content = user_client.get(reverse("schedule:types")).content.decode()
    assert "Cirurgia" in content
    assert "Exclusivo da B" not in content
    assert user_client.get(reverse("schedule:type_edit", args=[of_b.pk])).status_code == 404


def test_admin_creates_and_duplicate_name_is_refused(clinic_a, create_user, client_for):
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    url = reverse("schedule:type_new")
    assert (
        user_client.post(url, {"name": "Retorno", "color": "#112233", "active": "on"}).status_code
        == 302
    )
    response = user_client.post(url, {"name": "retorno", "color": "#112233"})
    assert response.status_code == 200
    assert "Já existe um tipo de atendimento com este nome" in response.content.decode()


def test_same_name_is_allowed_in_another_clinic(clinic_a, clinic_b, create_user, client_for):
    user_client = client_for(create_user("admin_b", clinic_b, Role.ADMIN))
    response = user_client.post(
        reverse("schedule:type_new"), {"name": "Retorno", "color": "#112233"}
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        AppointmentType.objects.create(name="Retorno", color="#445566")


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_reception_and_practitioner_only_view(role, clinic_a, create_user, client_for):
    user_client = client_for(create_user("usuario", clinic_a, role))
    with use_clinic(clinic_a):
        kind = AppointmentType.objects.first()
    assert user_client.get(reverse("schedule:types")).status_code == 200
    assert user_client.get(reverse("schedule:type_new")).status_code == 403
    assert user_client.post(reverse("schedule:type_delete", args=[kind.pk])).status_code == 403
    content = user_client.get(reverse("schedule:types")).content.decode()
    assert "Novo tipo" not in content


def test_registry_menu(clinic_a, create_user, client_for):
    content = client_for(create_user("recepcao", clinic_a)).get(reverse("home")).content.decode()
    for item in ["Cadastros", "Profissionais", "Tipos de atendimento", "Cidades", "Bancos"]:
        assert item in content
