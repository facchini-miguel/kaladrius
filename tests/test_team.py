"""Team management by the clinic administrator."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.core.models import Membership, Role
from apps.team.forms import MembershipForm

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "nova-senha-forte-789"


@pytest.fixture
def admin_a(clinic_a, create_user):
    return create_user("admin_a", clinic_a, Role.ADMIN)


@pytest.fixture
def clinic_admin_client(admin_a, client_for):
    return client_for(admin_a)


def new_data(**extra):
    return {
        "username": "carla",
        "first_name": "Carla",
        "last_name": "Mendes",
        "email": "carla@example.com",
        "role": Role.FRONT_DESK,
        "password1": NEW_PASSWORD,
        "password2": NEW_PASSWORD,
        **extra,
    }


def edit_data(role=Role.FRONT_DESK, active=True, **account):
    data = {"vinculo-role": role, **{f"conta-{k}": v for k, v in account.items()}}
    if active:
        data["vinculo-active"] = "on"
    return data


def test_only_clinic_admin_has_access(clinic_a, create_user, client_for):
    for role in (Role.FRONT_DESK, Role.PRACTITIONER):
        user_client = client_for(create_user(f"u_{role}", clinic_a, role))
        assert user_client.get(reverse("team:list")).status_code == 403
        assert "Equipe" not in user_client.get(reverse("home")).content.decode()


def test_list_shows_only_the_clinic_team(clinic_admin_client, clinic_a, clinic_b, create_user):
    create_user("recepcao_a", clinic_a)
    create_user("recepcao_b", clinic_b)
    content = clinic_admin_client.get(reverse("team:list")).content.decode()
    assert "recepcao_a" in content
    assert "recepcao_b" not in content


def test_creates_member_already_linked_to_clinic(clinic_admin_client, clinic_a, client):
    response = clinic_admin_client.post(reverse("team:new"), new_data())
    assert response.status_code == 302
    membership = Membership.objects.get(user__username="carla")
    assert (membership.clinic, membership.role, membership.active) == (
        clinic_a,
        Role.FRONT_DESK,
        True,
    )
    assert membership.user.check_password(NEW_PASSWORD)
    # The account creation shows up in the clinic's audit log.
    assert AuditEntry.objects.filter(
        clinic=clinic_a, action="criar", model_name="Usuário", object_repr="carla"
    ).exists()


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ({"username": "admin_a"}, "username"),
        ({"password2": "diferente-123456"}, "password2"),
        ({"password1": "123", "password2": "123"}, "password2"),
        ({"first_name": ""}, "first_name"),
    ],
)
def test_new_member_validations(clinic_admin_client, extra, field):
    response = clinic_admin_client.post(reverse("team:new"), new_data(**extra))
    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_changes_role_and_removes_access(clinic_admin_client, clinic_a, create_user, client_for):
    member = create_user("membro", clinic_a, Role.FRONT_DESK, first_name="Membro")
    membership = member.vinculos.get()
    url = reverse("team:edit", args=[membership.pk])
    clinic_admin_client.post(url, edit_data(Role.PRACTITIONER, first_name="Novo nome"))
    membership.refresh_from_db()
    member.refresh_from_db()
    assert membership.role == Role.PRACTITIONER
    assert member.first_name == "Novo nome"

    clinic_admin_client.post(
        url, edit_data(Role.PRACTITIONER, active=False, first_name="Novo nome")
    )
    membership.refresh_from_db()
    assert not membership.active
    # Without access the member no longer works in the clinic.
    response = client_for(member).get(reverse("patients:list"))
    assert response.status_code == 403


def test_does_not_change_own_role(clinic_admin_client, admin_a):
    membership = admin_a.vinculos.get()
    clinic_admin_client.post(
        reverse("team:edit", args=[membership.pk]),
        edit_data(Role.FRONT_DESK, active=False, first_name="Admin"),
    )
    membership.refresh_from_db()
    assert (membership.role, membership.active) == (Role.ADMIN, True)


def test_clinic_is_never_left_without_admin(clinic_a, create_user, client_for, django_user_model):
    only_admin = create_user("unico", clinic_a, Role.ADMIN, first_name="Único")
    superuser = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    user_client = client_for(superuser)
    membership = only_admin.vinculos.get()
    response = user_client.post(
        reverse("team:edit", args=[membership.pk]), edit_data(Role.FRONT_DESK)
    )
    assert "pelo menos um administrador ativo" in response.content.decode()
    membership.refresh_from_db()
    assert membership.role == Role.ADMIN


def test_admin_with_disabled_account_does_not_count(
    clinic_admin_client, admin_a, clinic_a, create_user
):
    disabled = create_user("desativado", clinic_a, Role.ADMIN, first_name="Desativado")
    disabled.is_active = False
    disabled.save()
    other = create_user("outro_admin", clinic_a, Role.ADMIN, first_name="Outro")
    # With "outro_admin" demoted, admin_a is still an active administrator.
    url = reverse("team:edit", args=[other.vinculos.get().pk])
    assert clinic_admin_client.post(url, edit_data(first_name="Outro")).status_code == 302

    # Now admin_a cannot be demoted: the only other administrator cannot log in.
    form = MembershipForm(
        {"role": Role.FRONT_DESK, "active": "on"}, instance=admin_a.vinculos.get(), editor=other
    )
    assert not form.is_valid()
    assert "pelo menos um administrador ativo" in str(form.errors)


def test_membership_of_another_clinic_gives_404(clinic_admin_client, clinic_b, create_user):
    membership = create_user("outro", clinic_b).vinculos.get()
    assert clinic_admin_client.get(reverse("team:edit", args=[membership.pk])).status_code == 404
    assert (
        clinic_admin_client.get(reverse("team:password", args=[membership.pk])).status_code == 404
    )


def test_sets_password_of_clinic_only_member(clinic_admin_client, clinic_a, create_user):
    member = create_user("membro", clinic_a)
    response = clinic_admin_client.post(
        reverse("team:password", args=[member.vinculos.get().pk]),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.check_password(NEW_PASSWORD)


def test_does_not_touch_account_of_who_works_elsewhere(
    clinic_admin_client, clinic_a, clinic_b, create_user
):
    member = create_user("multi", clinic_a, first_name="Multi")
    Membership.objects.create(user=member, clinic=clinic_b, role=Role.ADMIN)
    membership = member.vinculos.get(clinic=clinic_a)

    response = clinic_admin_client.post(
        reverse("team:password", args=[membership.pk]),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert not member.check_password(NEW_PASSWORD)

    # The role in this clinic can change, but not the name or e-mail of the account.
    clinic_admin_client.post(
        reverse("team:edit", args=[membership.pk]),
        edit_data(Role.PRACTITIONER, first_name="Trocado"),
    )
    member.refresh_from_db()
    membership.refresh_from_db()
    assert membership.role == Role.PRACTITIONER
    assert member.first_name == "Multi"


def test_does_not_touch_superuser_account(clinic_admin_client, clinic_a, django_user_model):
    superuser = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    membership = Membership.objects.create(user=superuser, clinic=clinic_a, role=Role.ADMIN)
    clinic_admin_client.post(
        reverse("team:password", args=[membership.pk]),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    superuser.refresh_from_db()
    assert not superuser.check_password(NEW_PASSWORD)


def test_own_password_goes_to_password_change(clinic_admin_client, admin_a):
    response = clinic_admin_client.get(reverse("team:password", args=[admin_a.vinculos.get().pk]))
    assert response.url == reverse("change_password")
