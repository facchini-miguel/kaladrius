"""Team management by the clinic administrator."""

import pytest
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.core.models import Papel, Vinculo

pytestmark = pytest.mark.django_db

NOVA_SENHA = "nova-senha-forte-789"


@pytest.fixture
def admin_a(clinica_a, criar_usuario):
    return criar_usuario("admin_a", clinica_a, Papel.ADMIN)


@pytest.fixture
def cliente_admin(admin_a, cliente_de):
    return cliente_de(admin_a)


def dados_novo(**extra):
    return {
        "username": "carla",
        "first_name": "Carla",
        "last_name": "Mendes",
        "email": "carla@example.com",
        "papel": Papel.RECEPCAO,
        "password1": NOVA_SENHA,
        "password2": NOVA_SENHA,
        **extra,
    }


def dados_edicao(papel=Papel.RECEPCAO, ativo=True, **conta):
    dados = {"vinculo-papel": papel, **{f"conta-{k}": v for k, v in conta.items()}}
    if ativo:
        dados["vinculo-ativo"] = "on"
    return dados


def test_so_o_administrador_da_clinica_acessa(clinica_a, criar_usuario, cliente_de):
    for papel in (Papel.RECEPCAO, Papel.PROFISSIONAL):
        cliente = cliente_de(criar_usuario(f"u_{papel}", clinica_a, papel))
        assert cliente.get(reverse("equipe:lista")).status_code == 403
        assert "Equipe" not in cliente.get(reverse("inicio")).content.decode()


def test_lista_mostra_so_a_equipe_da_clinica(cliente_admin, clinica_a, clinica_b, criar_usuario):
    criar_usuario("recepcao_a", clinica_a)
    criar_usuario("recepcao_b", clinica_b)
    conteudo = cliente_admin.get(reverse("equipe:lista")).content.decode()
    assert "recepcao_a" in conteudo
    assert "recepcao_b" not in conteudo


def test_cria_membro_ja_vinculado_a_clinica(cliente_admin, clinica_a, client):
    resposta = cliente_admin.post(reverse("equipe:novo"), dados_novo())
    assert resposta.status_code == 302
    vinculo = Vinculo.objects.get(usuario__username="carla")
    assert (vinculo.clinica, vinculo.papel, vinculo.ativo) == (clinica_a, Papel.RECEPCAO, True)
    assert vinculo.usuario.check_password(NOVA_SENHA)
    # The account creation shows up in the clinic's audit log.
    assert RegistroAuditoria.objects.filter(
        clinica=clinica_a, acao="criar", modelo="Usuário", objeto_descricao="carla"
    ).exists()


@pytest.mark.parametrize(
    ("extra", "campo"),
    [
        ({"username": "admin_a"}, "username"),
        ({"password2": "diferente-123456"}, "password2"),
        ({"password1": "123", "password2": "123"}, "password2"),
        ({"first_name": ""}, "first_name"),
    ],
)
def test_validacoes_do_novo_membro(cliente_admin, extra, campo):
    resposta = cliente_admin.post(reverse("equipe:novo"), dados_novo(**extra))
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors


def test_altera_perfil_e_tira_acesso(cliente_admin, clinica_a, criar_usuario, cliente_de):
    membro = criar_usuario("membro", clinica_a, Papel.RECEPCAO, first_name="Membro")
    vinculo = membro.vinculos.get()
    url = reverse("equipe:editar", args=[vinculo.pk])
    cliente_admin.post(url, dados_edicao(Papel.PROFISSIONAL, first_name="Novo nome"))
    vinculo.refresh_from_db()
    membro.refresh_from_db()
    assert vinculo.papel == Papel.PROFISSIONAL
    assert membro.first_name == "Novo nome"

    cliente_admin.post(url, dados_edicao(Papel.PROFISSIONAL, ativo=False, first_name="Novo nome"))
    vinculo.refresh_from_db()
    assert not vinculo.ativo
    # Without access the member no longer works in the clinic.
    resposta = cliente_de(membro).get(reverse("pacientes:lista"))
    assert resposta.status_code == 403


def test_nao_altera_o_proprio_perfil(cliente_admin, admin_a):
    vinculo = admin_a.vinculos.get()
    cliente_admin.post(
        reverse("equipe:editar", args=[vinculo.pk]),
        dados_edicao(Papel.RECEPCAO, ativo=False, first_name="Admin"),
    )
    vinculo.refresh_from_db()
    assert (vinculo.papel, vinculo.ativo) == (Papel.ADMIN, True)


def test_clinica_nao_fica_sem_administrador(
    clinica_a, criar_usuario, cliente_de, django_user_model
):
    unico_admin = criar_usuario("unico", clinica_a, Papel.ADMIN, first_name="Único")
    superusuario = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    cliente = cliente_de(superusuario)
    cliente.post(reverse("trocar_clinica"), {"clinica": clinica_a.pk})
    vinculo = unico_admin.vinculos.get()
    resposta = cliente.post(
        reverse("equipe:editar", args=[vinculo.pk]), dados_edicao(Papel.RECEPCAO)
    )
    assert "pelo menos um administrador ativo" in resposta.content.decode()
    vinculo.refresh_from_db()
    assert vinculo.papel == Papel.ADMIN


def test_vinculo_de_outra_clinica_da_404(cliente_admin, clinica_b, criar_usuario):
    vinculo = criar_usuario("outro", clinica_b).vinculos.get()
    assert cliente_admin.get(reverse("equipe:editar", args=[vinculo.pk])).status_code == 404
    assert cliente_admin.get(reverse("equipe:senha", args=[vinculo.pk])).status_code == 404


def test_define_senha_de_membro_exclusivo_da_clinica(cliente_admin, clinica_a, criar_usuario):
    membro = criar_usuario("membro", clinica_a)
    resposta = cliente_admin.post(
        reverse("equipe:senha", args=[membro.vinculos.get().pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    assert resposta.status_code == 302
    membro.refresh_from_db()
    assert membro.check_password(NOVA_SENHA)


def test_nao_mexe_na_conta_de_quem_atua_em_outra_clinica(
    cliente_admin, clinica_a, clinica_b, criar_usuario
):
    membro = criar_usuario("multi", clinica_a, first_name="Multi")
    Vinculo.objects.create(usuario=membro, clinica=clinica_b, papel=Papel.ADMIN)
    vinculo = membro.vinculos.get(clinica=clinica_a)

    resposta = cliente_admin.post(
        reverse("equipe:senha", args=[vinculo.pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    assert resposta.status_code == 302
    membro.refresh_from_db()
    assert not membro.check_password(NOVA_SENHA)

    # The role in this clinic can change, but not the name or e-mail of the account.
    cliente_admin.post(
        reverse("equipe:editar", args=[vinculo.pk]),
        dados_edicao(Papel.PROFISSIONAL, first_name="Trocado"),
    )
    membro.refresh_from_db()
    vinculo.refresh_from_db()
    assert vinculo.papel == Papel.PROFISSIONAL
    assert membro.first_name == "Multi"


def test_nao_mexe_na_conta_de_superusuario(cliente_admin, clinica_a, django_user_model):
    superusuario = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    vinculo = Vinculo.objects.create(usuario=superusuario, clinica=clinica_a, papel=Papel.ADMIN)
    cliente_admin.post(
        reverse("equipe:senha", args=[vinculo.pk]),
        {"new_password1": NOVA_SENHA, "new_password2": NOVA_SENHA},
    )
    superusuario.refresh_from_db()
    assert not superusuario.check_password(NOVA_SENHA)


def test_propria_senha_vai_para_a_troca_de_senha(cliente_admin, admin_a):
    resposta = cliente_admin.get(reverse("equipe:senha", args=[admin_a.vinculos.get().pk]))
    assert resposta.url == reverse("trocar_senha")
