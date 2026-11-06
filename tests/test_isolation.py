"""Clinic data isolation: no path may read or change another clinic's data."""

import pytest
from django.urls import reverse

from apps.core.isolation import (
    NoCurrentClinic,
    WrongClinic,
    use_clinic,
    without_isolation,
)
from apps.core.models import Role
from apps.practitioners.models import Practitioner

pytestmark = pytest.mark.django_db


# --- ORM level -------------------------------------------------------------------


def test_every_clinic_model_uses_isolated_manager_by_default():
    from django.apps import apps

    from apps.core.isolation import ClinicManager, ClinicModel

    templates_ = [m for m in apps.get_models() if issubclass(m, ClinicModel)]
    assert templates_, "no clinic model found"
    for template_ in templates_:
        assert isinstance(template_._default_manager, ClinicManager), template_.__name__
        assert isinstance(template_.objects, ClinicManager), template_.__name__


def test_no_current_clinic_fails_instead_of_showing_all(clinic_a, create_practitioner):
    create_practitioner(clinic_a, "Dra. A")
    with pytest.raises(NoCurrentClinic):
        list(Practitioner.objects.all())
    with pytest.raises(NoCurrentClinic):
        Practitioner.objects.count()


def test_query_sees_only_the_current_clinic(clinic_a, clinic_b, create_practitioner):
    create_practitioner(clinic_a, "Dra. A")
    create_practitioner(clinic_b, "Dr. B")
    with use_clinic(clinic_a):
        assert [p.name for p in Practitioner.objects.all()] == ["Dra. A"]
    with use_clinic(clinic_b):
        assert [p.name for p in Practitioner.objects.all()] == ["Dr. B"]


def test_lookup_by_id_of_another_clinic_finds_nothing(clinic_a, clinic_b, create_practitioner):
    of_b = create_practitioner(clinic_b, "Dr. B")
    with use_clinic(clinic_a), pytest.raises(Practitioner.DoesNotExist):
        Practitioner.objects.get(pk=of_b.pk)


def test_bulk_update_and_delete_respect_the_clinic(clinic_a, clinic_b, create_practitioner):
    create_practitioner(clinic_a, "Dra. A")
    create_practitioner(clinic_b, "Dr. B")
    with use_clinic(clinic_a):
        Practitioner.objects.update(active=False)
        Practitioner.objects.all().delete()
    with use_clinic(clinic_b):
        assert Practitioner.objects.get().active is True


def test_new_row_gets_the_current_clinic(clinic_a):
    with use_clinic(clinic_a):
        practitioner = Practitioner.objects.create(name="Dra. A")
    assert practitioner.clinic == clinic_a


def test_does_not_save_or_delete_row_of_another_clinic(clinic_a, clinic_b, create_practitioner):
    of_b = create_practitioner(clinic_b, "Dr. B")
    with use_clinic(clinic_a):
        of_b.name = "Alterado"
        with pytest.raises(WrongClinic):
            of_b.save()
        with pytest.raises(WrongClinic):
            of_b.delete()
    with use_clinic(clinic_b):
        assert Practitioner.objects.get(pk=of_b.pk).name == "Dr. B"


def test_create_without_current_clinic_fails():
    with pytest.raises(NoCurrentClinic):
        Practitioner(name="Sem clínica").save()


def test_without_isolation_sees_all_clinics(clinic_a, clinic_b, create_practitioner):
    create_practitioner(clinic_a, "Dra. A")
    create_practitioner(clinic_b, "Dr. B")
    with without_isolation():
        assert Practitioner.objects.count() == 2


# --- HTTP level ------------------------------------------------------------------


def test_list_shows_only_own_clinic(
    clinic_a, clinic_b, create_user, create_practitioner, client_for
):
    create_practitioner(clinic_a, "Dra. Ana da Clínica A")
    create_practitioner(clinic_b, "Dr. Bruno da Clínica B")
    user_client = client_for(create_user("ana", clinic_a))
    content = user_client.get(reverse("practitioners:list")).content.decode()
    assert "Dra. Ana da Clínica A" in content
    assert "Dr. Bruno da Clínica B" not in content


@pytest.mark.parametrize("route", ["practitioners:edit", "practitioners:delete"])
def test_url_with_id_of_another_clinic_gives_404(
    route, clinic_a, clinic_b, create_user, create_practitioner, client_for
):
    of_b = create_practitioner(clinic_b, "Dr. B")
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    url = reverse(route, args=[of_b.pk])
    assert user_client.get(url).status_code == 404
    assert user_client.post(url, {"name": "Invadido", "color": "#000000"}).status_code == 404
    with use_clinic(clinic_b):
        assert Practitioner.objects.get(pk=of_b.pk).name == "Dr. B"


def test_each_user_works_in_the_clinic_of_own_membership(
    clinic_a, clinic_b, create_user, create_practitioner, client_for
):
    # One installation serves one clinic (decision 069); the isolation still holds if the
    # database ever has another one: nobody chooses, each user gets their own clinic.
    create_practitioner(clinic_a, "Profissional A")
    create_practitioner(clinic_b, "Profissional B")
    content = client_for(create_user("ana", clinic_a)).get(reverse("practitioners:list"))
    content = content.content.decode()
    assert "Profissional A" in content and "Profissional B" not in content
    content = client_for(create_user("bia", clinic_b)).get(reverse("practitioners:list"))
    content = content.content.decode()
    assert "Profissional B" in content and "Profissional A" not in content


def test_inactive_membership_or_clinic_give_no_access(clinic_a, create_user, client_for):
    user = create_user("ana", clinic_a)
    user.memberships.update(active=False)
    assert client_for(user).get(reverse("practitioners:list")).status_code == 403

    user.memberships.update(active=True)
    clinic_a.active = False
    clinic_a.save()
    assert client_for(user).get(reverse("practitioners:list")).status_code == 403


def test_user_without_clinic_sees_warning(create_user, client_for):
    response = client_for(create_user("solto")).get(reverse("practitioners:list"))
    assert response.status_code == 403
    assert "não tem acesso a nenhuma clínica ativa" in response.content.decode()


def test_form_only_offers_users_of_own_clinic(clinic_a, clinic_b, create_user, client_for):
    create_user("colega_a", clinic_a)
    create_user("estranho_b", clinic_b)
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    content = user_client.get(reverse("practitioners:new")).content.decode()
    assert "colega_a" in content
    assert "estranho_b" not in content


def test_does_not_link_user_of_another_clinic_via_post(clinic_a, clinic_b, create_user, client_for):
    odd = create_user("estranho_b", clinic_b)
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    response = user_client.post(
        reverse("practitioners:new"),
        {"name": "Dr. Novo", "color": "#123456", "user": odd.pk, "active": "on"},
    )
    assert response.status_code == 200  # form redisplayed with an error
    with use_clinic(clinic_a):
        assert not Practitioner.objects.filter(name="Dr. Novo").exists()


def test_does_not_link_same_user_to_two_practitioners(
    clinic_a, create_user, create_practitioner, client_for
):
    colleague = create_user("colega_a", clinic_a)
    create_practitioner(clinic_a, "Dra. Primeira", user=colleague)
    user_client = client_for(create_user("admin_a", clinic_a, Role.ADMIN))
    response = user_client.post(
        reverse("practitioners:new"),
        {"name": "Dr. Segundo", "color": "#123456", "user": colleague.pk, "active": "on"},
    )
    assert "já está ligado a outro profissional" in response.content.decode()
    with use_clinic(clinic_a):
        assert not Practitioner.objects.filter(name="Dr. Segundo").exists()
