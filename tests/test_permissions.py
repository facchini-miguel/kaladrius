"""Role permissions: the server blocks forbidden actions and the screen hides them."""

import pytest
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.core.permissions import MATRIX, Action, Module
from apps.practitioners.models import Practitioner

pytestmark = pytest.mark.django_db


def test_matrix_covers_all_roles():
    assert set(MATRIX) == set(Role)
    assert all(actions == frozenset(Action) for actions in MATRIX[Role.ADMIN].values())
    assert set(MATRIX[Role.ADMIN]) == set(Module)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMIN, {"lista": 200, "novo": 200, "editar": 200, "excluir": 200}),
        (Role.FRONT_DESK, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
        (Role.PRACTITIONER, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
    ],
)
def test_practitioner_screens_access_by_role(
    role, expected, clinic_a, create_user, create_practitioner, client_for
):
    practitioner = create_practitioner(clinic_a, "Dra. A")
    user_client = client_for(create_user("usuario", clinic_a, role))
    urls = {
        "lista": reverse("practitioners:list"),
        "novo": reverse("practitioners:new"),
        "editar": reverse("practitioners:edit", args=[practitioner.pk]),
        "excluir": reverse("practitioners:delete", args=[practitioner.pk]),
    }
    for name, url in urls.items():
        assert user_client.get(url).status_code == expected[name], name


def test_reception_cannot_delete_even_by_post(
    clinic_a, create_user, create_practitioner, client_for
):
    practitioner = create_practitioner(clinic_a, "Dra. A")
    user_client = client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))
    response = user_client.post(reverse("practitioners:delete", args=[practitioner.pk]))
    assert response.status_code == 403
    with use_clinic(clinic_a):
        assert Practitioner.objects.filter(pk=practitioner.pk).exists()


def test_buttons_follow_the_permission(clinic_a, create_user, create_practitioner, client_for):
    create_practitioner(clinic_a, "Dra. A")
    reception = client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))
    content = reception.get(reverse("practitioners:list")).content.decode()
    assert "Novo profissional" not in content
    assert ">Editar<" not in content
    assert ">Excluir<" not in content

    admin = client_for(create_user("admin", clinic_a, Role.ADMIN))
    content = admin.get(reverse("practitioners:list")).content.decode()
    assert "Novo profissional" in content
    assert ">Editar<" in content
    assert ">Excluir<" in content


def test_clinic_admin_creates_edits_and_deletes(clinic_a, create_user, client_for):
    user_client = client_for(create_user("admin", clinic_a, Role.ADMIN))
    response = user_client.post(
        reverse("practitioners:new"),
        {"name": "Dr. Novo", "registration": "CRM 1", "color": "#123456", "active": "on"},
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        practitioner = Practitioner.objects.get(name="Dr. Novo")
    assert practitioner.clinic == clinic_a

    user_client.post(
        reverse("practitioners:edit", args=[practitioner.pk]),
        {"name": "Dr. Renomeado", "color": "#654321"},
    )
    practitioner.refresh_from_db()
    assert practitioner.name == "Dr. Renomeado"
    assert practitioner.active is False

    user_client.post(reverse("practitioners:delete", args=[practitioner.pk]))
    with use_clinic(clinic_a):
        assert not Practitioner.objects.exists()


def test_invalid_color_is_refused(clinic_a, create_user, client_for):
    user_client = client_for(create_user("admin", clinic_a, Role.ADMIN))
    response = user_client.post(reverse("practitioners:new"), {"name": "X", "color": "#zzzzzz"})
    assert response.status_code == 200
    assert "#RRGGBB" in response.content.decode()


def test_menu_shows_practitioners_only_with_permission(clinic_a, create_user, client_for):
    with_clinic = client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))
    assert "Profissionais</a>" in with_clinic.get(reverse("home")).content.decode()


def test_superuser_goes_straight_to_the_installation_clinic(
    clinic_a, create_practitioner, client_for, django_user_model
):
    practitioner = create_practitioner(clinic_a, "Dra. A")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    user_client = client_for(root)
    assert user_client.get(reverse("practitioners:edit", args=[practitioner.pk])).status_code == 200
    start = user_client.get(reverse("home")).content.decode()
    assert "Clínica A" in start and "Escolha" not in start


def test_first_access_registers_the_clinic(client_for, create_user, django_user_model):
    from apps.core.models import Clinic

    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    user_client = client_for(root)
    # Without a clinic, the superuser is sent to register it.
    response = user_client.get(reverse("practitioners:list"))
    assert response.url == reverse("register_clinic")

    response = user_client.post(
        reverse("register_clinic"), {"name": "Clínica Nova", "area": "medicina"}
    )
    assert response.url == reverse("home")
    assert list(Clinic.objects.values_list("name", "area")) == [("Clínica Nova", "medicina")]
    # A new clinic requires two-step verification (decision 112): the superuser turns it on.
    assert user_client.get(reverse("practitioners:list")).url == reverse("account:two_factor")
    from apps.account import services as account_services

    account_services.activate(account_services.prepare(root))
    assert user_client.get(reverse("practitioners:list")).status_code == 200
    # Only one: the page and the Django admin no longer add clinics.
    assert user_client.get(reverse("register_clinic")).url == reverse("home")
    user_client.post(reverse("register_clinic"), {"name": "Outra"})
    assert Clinic.objects.count() == 1
    assert user_client.get(reverse("admin:core_clinic_add")).status_code == 403
    # Other users may not register it (cliente_de logs this one in on the same client).
    assert client_for(create_user("ana")).get(reverse("register_clinic")).status_code == 403


def test_django_admin_only_for_superuser(clinic_a, create_user, client_for, django_user_model):
    staff = create_user("staff", clinic_a, Role.ADMIN, is_staff=True)
    response = client_for(staff).get(reverse("admin:index"))
    assert response.status_code == 302  # sent to the admin login

    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert client_for(root).get(reverse("admin:index")).status_code == 200


def test_django_admin_lists_practitioners_of_all_clinics(
    clinic_a, clinic_b, create_practitioner, client_for, django_user_model
):
    create_practitioner(clinic_a, "Dra. A")
    create_practitioner(clinic_b, "Dr. B")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    content = (
        client_for(root)
        .get(reverse("admin:profissionais_practitioner_changelist"))
        .content.decode()
    )
    assert "Dra. A" in content and "Dr. B" in content


def test_finance_role_sees_finance_and_nothing_else(clinic_a, create_user, client_for):
    """Decision 088: all of finance; patients, estimates and records only to look at."""
    user_client = client_for(create_user("financeiro", clinic_a, Role.FINANCE))
    for name in (
        "receivables",
        "payables",
        "cash_flow",
        "cash",
        "reports",
        "debtors",
        "commissions",
    ):
        assert user_client.get(reverse(f"finance:{name}")).status_code == 200, name
    for name in ("patients:list", "estimates:list", "practitioners:list"):
        assert user_client.get(reverse(name)).status_code == 200, name
    for name in (
        "schedule:calendar",
        "recalls:list",
        "team:list",
        "audit:list",
        "clinic_settings",
        "patients:new",
        "estimates:new",
    ):
        assert user_client.get(reverse(name)).status_code in (302, 403), name
    start = user_client.get(reverse("home"))
    assert start.status_code == 200
