"""Clinic data isolation: no path may read or change another clinic's data."""

import pytest
from django.urls import reverse

from apps.core.isolamento import (
    ClinicaDiferente,
    SemClinicaAtual,
    sem_isolamento,
    usar_clinica,
)
from apps.core.models import Papel
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


# --- ORM level -------------------------------------------------------------------


def test_todo_modelo_de_clinica_usa_o_gerenciador_isolado_como_padrao():
    from django.apps import apps

    from apps.core.isolamento import ClinicaManager, ModeloDaClinica

    modelos = [m for m in apps.get_models() if issubclass(m, ModeloDaClinica)]
    assert modelos, "no clinic model found"
    for modelo in modelos:
        assert isinstance(modelo._default_manager, ClinicaManager), modelo.__name__
        assert isinstance(modelo.objects, ClinicaManager), modelo.__name__


def test_sem_clinica_atual_falha_em_vez_de_mostrar_tudo(clinica_a, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    with pytest.raises(SemClinicaAtual):
        list(Profissional.objects.all())
    with pytest.raises(SemClinicaAtual):
        Profissional.objects.count()


def test_consulta_ve_somente_a_clinica_atual(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_a):
        assert [p.nome for p in Profissional.objects.all()] == ["Dra. A"]
    with usar_clinica(clinica_b):
        assert [p.nome for p in Profissional.objects.all()] == ["Dr. B"]


def test_busca_por_id_de_outra_clinica_nao_encontra(clinica_a, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_a), pytest.raises(Profissional.DoesNotExist):
        Profissional.objects.get(pk=de_b.pk)


def test_update_e_delete_em_massa_respeitam_a_clinica(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_a):
        Profissional.objects.update(ativo=False)
        Profissional.objects.all().delete()
    with usar_clinica(clinica_b):
        assert Profissional.objects.get().ativo is True


def test_novo_registro_recebe_a_clinica_atual(clinica_a):
    with usar_clinica(clinica_a):
        profissional = Profissional.objects.create(nome="Dra. A")
    assert profissional.clinica == clinica_a


def test_nao_salva_nem_exclui_registro_de_outra_clinica(clinica_a, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_a):
        de_b.nome = "Alterado"
        with pytest.raises(ClinicaDiferente):
            de_b.save()
        with pytest.raises(ClinicaDiferente):
            de_b.delete()
    with usar_clinica(clinica_b):
        assert Profissional.objects.get(pk=de_b.pk).nome == "Dr. B"


def test_criar_sem_clinica_atual_falha():
    with pytest.raises(SemClinicaAtual):
        Profissional(nome="Sem clínica").save()


def test_sem_isolamento_ve_todas_as_clinicas(clinica_a, clinica_b, criar_profissional):
    criar_profissional(clinica_a, "Dra. A")
    criar_profissional(clinica_b, "Dr. B")
    with sem_isolamento():
        assert Profissional.objects.count() == 2


# --- HTTP level ------------------------------------------------------------------


def test_lista_mostra_somente_a_propria_clinica(
    clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    criar_profissional(clinica_a, "Dra. Ana da Clínica A")
    criar_profissional(clinica_b, "Dr. Bruno da Clínica B")
    cliente = cliente_de(criar_usuario("ana", clinica_a))
    conteudo = cliente.get(reverse("profissionais:lista")).content.decode()
    assert "Dra. Ana da Clínica A" in conteudo
    assert "Dr. Bruno da Clínica B" not in conteudo


@pytest.mark.parametrize("rota", ["profissionais:editar", "profissionais:excluir"])
def test_url_com_id_de_outra_clinica_da_404(
    rota, clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    de_b = criar_profissional(clinica_b, "Dr. B")
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    url = reverse(rota, args=[de_b.pk])
    assert cliente.get(url).status_code == 404
    assert cliente.post(url, {"nome": "Invadido", "cor": "#000000"}).status_code == 404
    with usar_clinica(clinica_b):
        assert Profissional.objects.get(pk=de_b.pk).nome == "Dr. B"


def test_cada_usuario_trabalha_na_clinica_do_proprio_vinculo(
    clinica_a, clinica_b, criar_usuario, criar_profissional, cliente_de
):
    # One installation serves one clinic (decision 069); the isolation still holds if the
    # database ever has another one: nobody chooses, each user gets their own clinic.
    criar_profissional(clinica_a, "Profissional A")
    criar_profissional(clinica_b, "Profissional B")
    conteudo = cliente_de(criar_usuario("ana", clinica_a)).get(reverse("profissionais:lista"))
    conteudo = conteudo.content.decode()
    assert "Profissional A" in conteudo and "Profissional B" not in conteudo
    conteudo = cliente_de(criar_usuario("bia", clinica_b)).get(reverse("profissionais:lista"))
    conteudo = conteudo.content.decode()
    assert "Profissional B" in conteudo and "Profissional A" not in conteudo


def test_vinculo_inativo_ou_clinica_inativa_nao_dao_acesso(clinica_a, criar_usuario, cliente_de):
    usuario = criar_usuario("ana", clinica_a)
    usuario.vinculos.update(ativo=False)
    assert cliente_de(usuario).get(reverse("profissionais:lista")).status_code == 403

    usuario.vinculos.update(ativo=True)
    clinica_a.ativa = False
    clinica_a.save()
    assert cliente_de(usuario).get(reverse("profissionais:lista")).status_code == 403


def test_usuario_sem_clinica_ve_aviso(criar_usuario, cliente_de):
    resposta = cliente_de(criar_usuario("solto")).get(reverse("profissionais:lista"))
    assert resposta.status_code == 403
    assert "não tem acesso a nenhuma clínica ativa" in resposta.content.decode()


def test_formulario_so_oferece_usuarios_da_propria_clinica(
    clinica_a, clinica_b, criar_usuario, cliente_de
):
    criar_usuario("colega_a", clinica_a)
    criar_usuario("estranho_b", clinica_b)
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    conteudo = cliente.get(reverse("profissionais:novo")).content.decode()
    assert "colega_a" in conteudo
    assert "estranho_b" not in conteudo


def test_nao_liga_usuario_de_outra_clinica_via_post(
    clinica_a, clinica_b, criar_usuario, cliente_de
):
    estranho = criar_usuario("estranho_b", clinica_b)
    cliente = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    resposta = cliente.post(
        reverse("profissionais:novo"),
        {"nome": "Dr. Novo", "cor": "#123456", "usuario": estranho.pk, "ativo": "on"},
    )
    assert resposta.status_code == 200  # form redisplayed with an error
    with usar_clinica(clinica_a):
        assert not Profissional.objects.filter(nome="Dr. Novo").exists()
