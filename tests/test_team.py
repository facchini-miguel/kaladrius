"""Team management by the clinic administrator."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.core.models import Membership, Role
from apps.team.forms import MembershipForm

pytestmark = pytest.mark.django_db

NOVA_SENHA = "nova-senha-forte-789"


@pytest.fixture
def admin_a(clinica_a, criar_usuario):
    return criar_usuario("admin_a", clinica_a, Role.ADMIN)


@pytest.fixture
def cliente_admin(admin_a, cliente_de):
    return cliente_de(admin_a)


def dados_novo(**extra):
    return {
        "username": "carla",
        "first_name": "Carla",
        "last_name": "Mendes",
        "email": "carla@example.com",
        "role": Role.FRONT_DESK,
        "password1": NOVA_SENHA,
        "password2": NOVA_SENHA,
        **extra,
    }


def dados_edicao(role=Role.FRONT_DESK, active=True, **account):
    data = {"vinculo-role": role, **{f"conta-{k}": v for k, v in account.items()}}
    if active:
        data["vinculo-active"] = "on"
    return data


def test_only_clinic_admin_has_access(clinica_a, criar_usuario, cliente_de):
    for role in (Role.FRONT_DESK, Role.PRACTITIONER):
        cliente = cliente_de(criar_usuario(f"u_{role}", clinica_a, role))
        assert cliente.get(reverse("team:list")).status_code == 403
        assert "Equipe" not in cliente.get(reverse("home")).content.decode()


def test_list_shows_only_the_clinic_team(cliente_admin, clinica_a, clinica_b, criar_usuario):
    criar_usuario("recepcao_a", clinica_a)
    criar_usuario("recepcao_b", clinica_b)
    content = cliente_admin.get(reverse("team:list")).content.decode()
    assert "recepcao_a" in content
    assert "recepcao_b" not in content


def test_creates_member_already_linked_to_clinic(cliente_admin, clinica_a, client):
    response = cliente_admin.post(reverse("team:new"), dados_novo())
    assert response.status_code == 302
    vinculo = Membership.objects.get(user__username="carla")
    assert (vinculo.clinic, vinculo.role, vinculo.active) == (clinica_a, Role.FRONT_DESK, True)
    assert vinculo.user.check_password(NOVA_SENHA)
    # The account creation shows up in the clinic's audit log.
    assert AuditEntry.objects.filter(
        clinic=clinica_a, action="criar", model_name="Usuário", object_repr="carla"
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
def test_new_member_validations(cliente_admin, extra, field):
    response = cliente_admin.post(reverse("team:new"), dados_novo(**extra))
    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_changes_role_and_removes_access(cliente_admin, clinica_a, criar_usuario, cliente_de):
    membro = criar_usuario("membro", clinica_a, Role.FRONT_DESK, first_name="Membro")
    vinculo = membro.vinculos.get()
    url = reverse("team:edit", args=[vinculo.pk])
    cliente_admin.post(url, dados_edicao(Role.PRACTITIONER, first_name="Novo nome"))
    vinculo.refresh_from_db()
    membro.refresh_from_db()
    assert vinculo.role == Role.PRACTITIONER
    assert membro.first_name == "Novo nome"

    cliente_admin.post(url, dados_edicao(Role.PRACTITIONER, active=False, first_name="Novo nome"))
    vinculo.refresh_from_db()
    assert not vinculo.active
    # Without access the member no longer works in the clinic.
    response = cliente_de(membro).get(reverse("patients:list"))
    assert response.status_code == 403


def test_does_not_change_own_role(cliente_admin, admin_a):
    vinculo = admin_a.vinculos.get()
    cliente_admin.post(
        reverse("team:edit", args=[vinculo.pk]),
        dados_edicao(Role.FRONT_DESK, active=False, first_name="Admin"),
    )
    vinculo.refresh_from_db()
    assert (vinculo.role, vinculo.active) == (Role.ADMIN, True)


def test_clinic_is_never_left_without_admin(
    clinica_a, criar_usuario, cliente_de, django_user_model
):
    unico_admin = criar_usuario("unico", clinica_a, Role.ADMIN, first_name="Único")
    superusuario = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    cliente = cliente_de(superusuario)
    vinculo = unico_admin.vinculos.get()
    response = cliente.post(reverse("team:edit", args=[vinculo.pk]), dados_edicao(Role.FRONT_DESK))
    assert "pelo menos um administrador ativo" in response.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.role == Role.ADMIN


def test_admin_with_disabled_account_does_not_count(
    cliente_admin, admin_a, clinica_a, criar_usuario
):
    desativado = criar_usuario("desativado", clinica_a, Role.ADMIN, first_name="Desativado")
    desativado.is_active = False
    desativado.save()
    other = criar_usuario("outro_admin", clinica_a, Role.ADMIN, first_name="Outro")
    # With "outro_admin" demoted, admin_a is still an active administrator.
    url = reverse("team:edit", args=[other.vinculos.get().pk])
    assert cliente_admin.post(url, dados_edicao(first_name="Outro")).status_code == 302

    # Now admin_a cannot be demoted: the only other administrator cannot log in.
    form = MembershipForm(
        {"role": Role.FRONT_DESK, "active": "on"}, instance=admin_a.vinculos.get(), editor=other
    )
    assert not form.is_valid()
    assert "pelo menos um administrador ativo" in str(form.errors)


def test_membership_of_another_clinic_gives_404(cliente_admin, clinica_b, criar_usuario):
    vinculo = criar_usuario("outro", clinica_b).vinculos.get()
    assert cliente_admin.get(reverse("team:edit", args=[vinculo.pk])).status_code == 404
    assert cliente_admin.get(reverse("team:password", args=[vinculo.pk])).status_code == 404


def test_sets_password_of_clinic_only_member(cliente_admin, clinica_a, criar_usuario):
    membro = criar_usuario("membro", clinica_a)
    response = cliente_admin.post(
        reverse("team:password", args=[membro.vinculos.get().pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    assert response.status_code == 302
    membro.refresh_from_db()
    assert membro.check_password(NOVA_SENHA)


def test_does_not_touch_account_of_who_works_elsewhere(
    cliente_admin, clinica_a, clinica_b, criar_usuario
):
    membro = criar_usuario("multi", clinica_a, first_name="Multi")
    Membership.objects.create(user=membro, clinic=clinica_b, role=Role.ADMIN)
    vinculo = membro.vinculos.get(clinic=clinica_a)

    response = cliente_admin.post(
        reverse("team:password", args=[vinculo.pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    assert response.status_code == 302
    membro.refresh_from_db()
    assert not membro.check_password(NOVA_SENHA)

    # The role in this clinic can change, but not the name or e-mail of the account.
    cliente_admin.post(
        reverse("team:edit", args=[vinculo.pk]),
        dados_edicao(Role.PRACTITIONER, first_name="Trocado"),
    )
    membro.refresh_from_db()
    vinculo.refresh_from_db()
    assert vinculo.role == Role.PRACTITIONER
    assert membro.first_name == "Multi"


def test_does_not_touch_superuser_account(cliente_admin, clinica_a, django_user_model):
    superusuario = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    vinculo = Membership.objects.create(user=superusuario, clinic=clinica_a, role=Role.ADMIN)
    cliente_admin.post(
        reverse("team:password", args=[vinculo.pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    superusuario.refresh_from_db()
    assert not superusuario.check_password(NOVA_SENHA)


def test_own_password_goes_to_password_change(cliente_admin, admin_a):
    response = cliente_admin.get(reverse("team:password", args=[admin_a.vinculos.get().pk]))
    assert response.url == reverse("change_password")
