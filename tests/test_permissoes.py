"""Role permissions: the server blocks forbidden actions and the screen hides them."""

import pytest
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.core.permissoes import MATRIZ, Acao, Modulo
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


def test_matriz_cobre_todos_os_papeis():
    assert set(MATRIZ) == set(Papel)
    assert all(acoes == frozenset(Acao) for acoes in MATRIZ[Papel.ADMIN].values())
    assert set(MATRIZ[Papel.ADMIN]) == set(Modulo)


@pytest.mark.parametrize(
    ("papel", "esperado"),
    [
        (Papel.ADMIN, {"lista": 200, "novo": 200, "editar": 200, "excluir": 200}),
        (Papel.RECEPCAO, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
        (Papel.PROFISSIONAL, {"lista": 200, "novo": 403, "editar": 403, "excluir": 403}),
    ],
)
def test_acesso_as_telas_de_profissionais_por_papel(
    papel, esperado, clinica_a, criar_usuario, criar_profissional, cliente_de
):
    profissional = criar_profissional(clinica_a, "Dra. A")
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    urls = {
        "lista": reverse("profissionais:lista"),
        "novo": reverse("profissionais:novo"),
        "editar": reverse("profissionais:editar", args=[profissional.pk]),
        "excluir": reverse("profissionais:excluir", args=[profissional.pk]),
    }
    for nome, url in urls.items():
        assert cliente.get(url).status_code == esperado[nome], nome


def test_recepcao_nao_exclui_nem_por_post(clinica_a, criar_usuario, criar_profissional, cliente_de):
    profissional = criar_profissional(clinica_a, "Dra. A")
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    resposta = cliente.post(reverse("profissionais:excluir", args=[profissional.pk]))
    assert resposta.status_code == 403
    with usar_clinica(clinica_a):
        assert Profissional.objects.filter(pk=profissional.pk).exists()


def test_botoes_aparecem_conforme_a_permissao(
    clinica_a, criar_usuario, criar_profissional, cliente_de
):
    criar_profissional(clinica_a, "Dra. A")
    recepcao = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    conteudo = recepcao.get(reverse("profissionais:lista")).content.decode()
    assert "Novo profissional" not in conteudo
    assert ">Editar<" not in conteudo
    assert ">Excluir<" not in conteudo

    admin = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    conteudo = admin.get(reverse("profissionais:lista")).content.decode()
    assert "Novo profissional" in conteudo
    assert ">Editar<" in conteudo
    assert ">Excluir<" in conteudo


def test_admin_da_clinica_cria_edita_e_exclui(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    resposta = cliente.post(
        reverse("profissionais:novo"),
        {"nome": "Dr. Novo", "registro": "CRM 1", "cor": "#123456", "ativo": "on"},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        profissional = Profissional.objects.get(nome="Dr. Novo")
    assert profissional.clinica == clinica_a

    cliente.post(
        reverse("profissionais:editar", args=[profissional.pk]),
        {"nome": "Dr. Renomeado", "cor": "#654321"},
    )
    profissional.refresh_from_db()
    assert profissional.nome == "Dr. Renomeado"
    assert profissional.ativo is False

    cliente.post(reverse("profissionais:excluir", args=[profissional.pk]))
    with usar_clinica(clinica_a):
        assert not Profissional.objects.exists()


def test_cor_invalida_e_recusada(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    resposta = cliente.post(reverse("profissionais:novo"), {"nome": "X", "cor": "#zzzzzz"})
    assert resposta.status_code == 200
    assert "#RRGGBB" in resposta.content.decode()


def test_menu_mostra_profissionais_so_com_permissao(clinica_a, criar_usuario, cliente_de):
    com_clinica = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    assert "Profissionais</a>" in com_clinica.get(reverse("inicio")).content.decode()


def test_superusuario_pode_tudo_na_clinica_escolhida(
    clinica_a, criar_profissional, cliente_de, django_user_model
):
    profissional = criar_profissional(clinica_a, "Dra. A")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    cliente = cliente_de(root)

    # Without a chosen clinic, the superuser is sent to the clinic picker.
    resposta = cliente.get(reverse("profissionais:lista"))
    assert resposta.status_code == 302
    assert reverse("trocar_clinica") in resposta.url

    cliente.post(reverse("trocar_clinica"), {"clinica": clinica_a.pk})
    assert cliente.get(reverse("profissionais:editar", args=[profissional.pk])).status_code == 200


def test_admin_do_django_so_para_superusuario(
    clinica_a, criar_usuario, cliente_de, django_user_model
):
    staff = criar_usuario("staff", clinica_a, Papel.ADMIN, is_staff=True)
    resposta = cliente_de(staff).get(reverse("admin:index"))
    assert resposta.status_code == 302  # sent to the admin login

    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert cliente_de(root).get(reverse("admin:index")).status_code == 200


def test_admin_do_django_lista_profissionais_de_todas_as_clinicas(
    clinica_a, clinica_b, criar_profissional, cliente_de, django_user_model
):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    conteudo = (
        cliente_de(root)
        .get(reverse("admin:profissionais_profissional_changelist"))
        .content.decode()
    )
    assert "Dra. A" in conteudo and "Dr. B" in conteudo
