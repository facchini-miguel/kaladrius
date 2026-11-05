"""Role permissions: the server blocks forbidden actions and the screen hides them."""

import pytest
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.core.permissions import MATRIZ, Acao, Modulo
from apps.practitioners.models import Practitioner

pytestmark = pytest.mark.django_db


def test_matriz_cobre_todos_os_papeis():
    assert set(MATRIZ) == set(Papel)
    assert all(acoes == frozenset(Acao) for acoes in MATRIZ[Papel.ADMIN].values())
    assert set(MATRIZ[Papel.ADMIN]) == set(Modulo)


@pytest.mark.parametrize(
    ("role", "esperado"),
    [
        (Papel.ADMIN, {"lista": 200, "novo": 200, "editar": 200, "excluir": 200}),
        (Papel.RECEPCAO, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
        (Papel.PROFISSIONAL, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
    ],
)
def test_acesso_as_telas_de_profissionais_por_papel(
    role, esperado, clinica_a, criar_usuario, criar_profissional, cliente_de
):
    practitioner = criar_profissional(clinica_a, "Dra. A")
    cliente = cliente_de(criar_usuario("usuario", clinica_a, role))
    urls = {
        "lista": reverse("practitioners:list"),
        "novo": reverse("practitioners:new"),
        "editar": reverse("practitioners:edit", args=[practitioner.pk]),
        "excluir": reverse("practitioners:delete", args=[practitioner.pk]),
    }
    for name, url in urls.items():
        assert cliente.get(url).status_code == esperado[name], name


def test_recepcao_nao_exclui_nem_por_post(clinica_a, criar_usuario, criar_profissional, cliente_de):
    practitioner = criar_profissional(clinica_a, "Dra. A")
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    response = cliente.post(reverse("practitioners:delete", args=[practitioner.pk]))
    assert response.status_code == 403
    with usar_clinica(clinica_a):
        assert Practitioner.objects.filter(pk=practitioner.pk).exists()


def test_botoes_aparecem_conforme_a_permissao(
    clinica_a, criar_usuario, criar_profissional, cliente_de
):
    criar_profissional(clinica_a, "Dra. A")
    reception = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    content = reception.get(reverse("practitioners:list")).content.decode()
    assert "Novo profissional" not in content
    assert ">Editar<" not in content
    assert ">Excluir<" not in content

    admin = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    content = admin.get(reverse("practitioners:list")).content.decode()
    assert "Novo profissional" in content
    assert ">Editar<" in content
    assert ">Excluir<" in content


def test_admin_da_clinica_cria_edita_e_exclui(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    response = cliente.post(
        reverse("practitioners:new"),
        {"name": "Dr. Novo", "registration": "CRM 1", "color": "#123456", "active": "on"},
    )
    assert response.status_code == 302
    with usar_clinica(clinica_a):
        practitioner = Practitioner.objects.get(name="Dr. Novo")
    assert practitioner.clinic == clinica_a

    cliente.post(
        reverse("practitioners:edit", args=[practitioner.pk]),
        {"name": "Dr. Renomeado", "color": "#654321"},
    )
    practitioner.refresh_from_db()
    assert practitioner.name == "Dr. Renomeado"
    assert practitioner.active is False

    cliente.post(reverse("practitioners:delete", args=[practitioner.pk]))
    with usar_clinica(clinica_a):
        assert not Practitioner.objects.exists()


def test_cor_invalida_e_recusada(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    response = cliente.post(reverse("practitioners:new"), {"name": "X", "color": "#zzzzzz"})
    assert response.status_code == 200
    assert "#RRGGBB" in response.content.decode()


def test_menu_mostra_profissionais_so_com_permissao(clinica_a, criar_usuario, cliente_de):
    com_clinica = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    assert "Profissionais</a>" in com_clinica.get(reverse("home")).content.decode()


def test_superusuario_entra_direto_na_clinica_da_instalacao(
    clinica_a, criar_profissional, cliente_de, django_user_model
):
    practitioner = criar_profissional(clinica_a, "Dra. A")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    cliente = cliente_de(root)
    assert cliente.get(reverse("practitioners:edit", args=[practitioner.pk])).status_code == 200
    start = cliente.get(reverse("home")).content.decode()
    assert "Clínica A" in start and "Escolha" not in start


def test_primeiro_acesso_cadastra_a_clinica(cliente_de, criar_usuario, django_user_model):
    from apps.core.models import Clinic

    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    cliente = cliente_de(root)
    # Without a clinic, the superuser is sent to register it.
    response = cliente.get(reverse("practitioners:list"))
    assert response.url == reverse("register_clinic")

    response = cliente.post(
        reverse("register_clinic"), {"name": "Clínica Nova", "area": "medicina"}
    )
    assert response.url == reverse("home")
    assert list(Clinic.objects.values_list("name", "area")) == [("Clínica Nova", "medicina")]
    # A new clinic requires two-step verification (decision 112): the superuser turns it on.
    assert cliente.get(reverse("practitioners:list")).url == reverse("account:two_factor")
    from apps.account import services as conta_servicos

    conta_servicos.ativar(conta_servicos.preparar(root))
    assert cliente.get(reverse("practitioners:list")).status_code == 200
    # Only one: the page and the Django admin no longer add clinics.
    assert cliente.get(reverse("register_clinic")).url == reverse("home")
    cliente.post(reverse("register_clinic"), {"name": "Outra"})
    assert Clinic.objects.count() == 1
    assert cliente.get(reverse("admin:core_clinic_add")).status_code == 403
    # Other users may not register it (cliente_de logs this one in on the same client).
    assert cliente_de(criar_usuario("ana")).get(reverse("register_clinic")).status_code == 403


def test_admin_do_django_so_para_superusuario(
    clinica_a, criar_usuario, cliente_de, django_user_model
):
    staff = criar_usuario("staff", clinica_a, Papel.ADMIN, is_staff=True)
    response = cliente_de(staff).get(reverse("admin:index"))
    assert response.status_code == 302  # sent to the admin login

    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert cliente_de(root).get(reverse("admin:index")).status_code == 200


def test_admin_do_django_lista_profissionais_de_todas_as_clinicas(
    clinica_a, clinica_b, criar_profissional, cliente_de, django_user_model
):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    content = (
        cliente_de(root)
        .get(reverse("admin:profissionais_practitioner_changelist"))
        .content.decode()
    )
    assert "Dra. A" in content and "Dr. B" in content


def test_perfil_financeiro_ve_o_financeiro_e_nada_mais(clinica_a, criar_usuario, cliente_de):
    """Decision 088: all of finance; patients, estimates and records only to look at."""
    cliente = cliente_de(criar_usuario("financeiro", clinica_a, Papel.FINANCEIRO))
    for name in (
        "receivables",
        "payables",
        "cash_flow",
        "cash",
        "reports",
        "debtors",
        "commissions",
    ):
        assert cliente.get(reverse(f"finance:{name}")).status_code == 200, name
    for name in ("patients:list", "estimates:list", "practitioners:list"):
        assert cliente.get(reverse(name)).status_code == 200, name
    for name in (
        "schedule:calendar",
        "recalls:list",
        "team:list",
        "audit:list",
        "clinic_settings",
        "patients:new",
        "estimates:new",
    ):
        assert cliente.get(reverse(name)).status_code in (302, 403), name
    start = cliente.get(reverse("home"))
    assert start.status_code == 200
