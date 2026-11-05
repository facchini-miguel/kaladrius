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

    modelos = [m for m in apps.get_models() if issubclass(m, ClinicModel)]
    assert modelos, "no clinic model found"
    for modelo in modelos:
        assert isinstance(modelo._default_manager, ClinicManager), modelo.__name__
        assert isinstance(modelo.objects, ClinicManager), modelo.__name__


def test_no_current_clinic_fails_instead_of_showing_all(clinica_a, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    with pytest.raises(NoCurrentClinic):
        list(Practitioner.objects.all())
    with pytest.raises(NoCurrentClinic):
        Practitioner.objects.count()


def test_query_sees_only_the_current_clinic(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with use_clinic(clinica_a):
        assert [p.name for p in Practitioner.objects.all()] == ["Dra. A"]
    with use_clinic(clinica_b):
        assert [p.name for p in Practitioner.objects.all()] == ["Dr. B"]


def test_lookup_by_id_of_another_clinic_finds_nothing(clinica_a, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with use_clinic(clinica_a), pytest.raises(Practitioner.DoesNotExist):
        Practitioner.objects.get(pk=de_b.pk)


def test_bulk_update_and_delete_respect_the_clinic(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with use_clinic(clinica_a):
        Practitioner.objects.update(active=False)
        Practitioner.objects.all().delete()
    with use_clinic(clinica_b):
        assert Practitioner.objects.get().active is True


def test_new_row_gets_the_current_clinic(clinica_a):
    with use_clinic(clinica_a):
        practitioner = Practitioner.objects.create(name="Dra. A")
    assert practitioner.clinic == clinica_a


def test_does_not_save_or_delete_row_of_another_clinic(clinica_a, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with use_clinic(clinica_a):
        de_b.name = "Alterado"
        with pytest.raises(WrongClinic):
            de_b.save()
        with pytest.raises(WrongClinic):
            de_b.delete()
    with use_clinic(clinica_b):
        assert Practitioner.objects.get(pk=de_b.pk).name == "Dr. B"


def test_create_without_current_clinic_fails():
    with pytest.raises(NoCurrentClinic):
        Practitioner(name="Sem clínica").save()


def test_without_isolation_sees_all_clinics(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with without_isolation():
        assert Practitioner.objects.count() == 2


# --- HTTP level ------------------------------------------------------------------


def test_list_shows_only_own_clinic(
    clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    criar_profissional(clinica_a, "Dra. Ana da Clínica A")
    criar_profissional(clinica_b, "Dr. Bruno da Clínica B")
    cliente = cliente_de(criar_usuario("ana", clinica_a))
    content = cliente.get(reverse("practitioners:list")).content.decode()
    assert "Dra. Ana da Clínica A" in content
    assert "Dr. Bruno da Clínica B" not in content


@pytest.mark.parametrize("rota", ["practitioners:edit", "practitioners:delete"])
def test_url_with_id_of_another_clinic_gives_404(
    rota, clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    de_b = criar_profissional(clinica_b, "Dr. B")
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    url = reverse(rota, args=[de_b.pk])
    assert cliente.get(url).status_code == 404
    assert cliente.post(url, {"name": "Invadido", "color": "#000000"}).status_code == 404
    with use_clinic(clinica_b):
        assert Practitioner.objects.get(pk=de_b.pk).name == "Dr. B"


def test_each_user_works_in_the_clinic_of_own_membership(
    clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    # One installation serves one clinic (decision 069); the isolation still holds if the
    # database ever has another one: nobody chooses, each user gets their own clinic.
    criar_profissional(clinica_a, "Profissional A")
    criar_profissional(clinica_b, "Profissional B")
    content = cliente_de(criar_usuario("ana", clinica_a)).get(reverse("practitioners:list"))
    content = content.content.decode()
    assert "Profissional A" in content and "Profissional B" not in content
    content = cliente_de(criar_usuario("bia", clinica_b)).get(reverse("practitioners:list"))
    content = content.content.decode()
    assert "Profissional B" in content and "Profissional A" not in content


def test_inactive_membership_or_clinic_give_no_access(clinica_a, criar_usuario, cliente_de):
    user = criar_usuario("ana", clinica_a)
    user.vinculos.update(active=False)
    assert cliente_de(user).get(reverse("practitioners:list")).status_code == 403

    user.vinculos.update(active=True)
    clinica_a.active = False
    clinica_a.save()
    assert cliente_de(user).get(reverse("practitioners:list")).status_code == 403


def test_user_without_clinic_sees_warning(criar_usuario, cliente_de):
    response = cliente_de(criar_usuario("solto")).get(reverse("practitioners:list"))
    assert response.status_code == 403
    assert "não tem acesso a nenhuma clínica ativa" in response.content.decode()


def test_form_only_offers_users_of_own_clinic(clinica_a, clinica_b, criar_usuario, cliente_de):
    criar_usuario("colega_a", clinica_a)
    criar_usuario("estranho_b", clinica_b)
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    content = cliente.get(reverse("practitioners:new")).content.decode()
    assert "colega_a" in content
    assert "estranho_b" not in content


def test_does_not_link_user_of_another_clinic_via_post(
    clinica_a, clinica_b, criar_usuario, cliente_de
):
    estranho = criar_usuario("estranho_b", clinica_b)
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    response = cliente.post(
        reverse("practitioners:new"),
        {"name": "Dr. Novo", "color": "#123456", "user": estranho.pk, "active": "on"},
    )
    assert response.status_code == 200  # form redisplayed with an error
    with use_clinic(clinica_a):
        assert not Practitioner.objects.filter(name="Dr. Novo").exists()


def test_does_not_link_same_user_to_two_practitioners(
    clinica_a, criar_usuario, criar_profissional, cliente_de
):
    colega = criar_usuario("colega_a", clinica_a)
    criar_profissional(clinica_a, "Dra. Primeira", user=colega)
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))
    response = cliente.post(
        reverse("practitioners:new"),
        {"name": "Dr. Segundo", "color": "#123456", "user": colega.pk, "active": "on"},
    )
    assert "já está ligado a outro profissional" in response.content.decode()
    with use_clinic(clinica_a):
        assert not Practitioner.objects.filter(name="Dr. Segundo").exists()
