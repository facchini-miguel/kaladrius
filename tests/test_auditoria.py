import datetime

import pytest
from axes.models import AccessAttempt
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db
Acao = RegistroAuditoria.Acao


@pytest.fixture
def admin_a(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))


def ultimos(**filtros):
    return list(RegistroAuditoria.objects.filter(**filtros).order_by("pk"))


def test_criacao_alteracao_e_exclusao_ficam_registradas(admin_a, clinica_a):
    admin_a.post(reverse("pacientes:novo"), {"tipo": "PF", "nome": "Maria", "ativo": "on"})
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.get(nome="Maria")
    [criacao] = ultimos(acao=Acao.CRIAR, modelo="Paciente")
    assert criacao.usuario_nome == "admin_a"
    assert criacao.clinica_id == clinica_a.pk
    assert criacao.objeto_id == str(paciente.pk)
    assert criacao.alteracoes["nome"] == [None, "Maria"]
    assert criacao.ip == "127.0.0.1"

    admin_a.post(
        reverse("pacientes:editar", args=[paciente.pk]),
        {"tipo": "PF", "nome": "Maria Souza", "ativo": "on", "profissao": "Professora"},
    )
    [alteracao] = ultimos(acao=Acao.ALTERAR, modelo="Paciente")
    assert alteracao.alteracoes == {
        "nome": ["Maria", "Maria Souza"],
        "profissao": ["", "Professora"],
    }

    admin_a.post(reverse("pacientes:excluir", args=[paciente.pk]))
    [exclusao] = ultimos(acao=Acao.EXCLUIR, modelo="Paciente")
    assert exclusao.alteracoes["nome"] == ["Maria Souza", None]


def test_salvar_sem_mudancas_nao_gera_registro(clinica_a):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Sem mudança")
        paciente.save()
    assert not ultimos(acao=Acao.ALTERAR, modelo="Paciente")


def test_abrir_a_ficha_fica_registrado(admin_a, clinica_a):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Consultado")
    admin_a.get(reverse("pacientes:ficha", args=[paciente.pk]))
    [visualizacao] = ultimos(acao=Acao.VISUALIZAR)
    assert visualizacao.objeto_descricao == "Consultado"
    assert visualizacao.usuario_nome == "admin_a"


def test_login_e_tentativa_recusada_ficam_registrados(client, criar_usuario):
    criar_usuario("maria")
    client.post(reverse("login"), {"username": "maria", "password": "errada"})
    [falha] = ultimos(acao=Acao.LOGIN_FALHOU)
    assert falha.objeto_descricao == "usuário informado: maria"
    assert "errada" not in str(falha.alteracoes) + falha.objeto_descricao

    client.post(reverse("login"), {"username": "maria", "password": "senha-de-teste-123"})
    [entrada] = ultimos(acao=Acao.LOGIN)
    assert entrada.usuario_nome == "maria"


def test_senha_nunca_e_gravada(criar_usuario):
    usuario = criar_usuario("joao")
    usuario.set_password("nova-senha-secreta-123")
    usuario.save()
    registros = RegistroAuditoria.objects.filter(modelo="Usuário")
    texto = " ".join(str(r.alteracoes) for r in registros)
    assert "argon2" not in texto and "nova-senha" not in texto
    [alteracao] = registros.filter(acao=Acao.ALTERAR)
    assert alteracao.alteracoes == {"senha": ["(oculta)", "(alterada)"]}


def test_tela_mostra_somente_a_clinica_atual(admin_a, clinica_a, clinica_b):
    with usar_clinica(clinica_a):
        Paciente.objects.create(nome="Paciente da A")
    with usar_clinica(clinica_b):
        Paciente.objects.create(nome="Paciente da B")
    conteudo = admin_a.get(reverse("auditoria:lista"), {"modelo": "Paciente"}).content.decode()
    assert "Paciente da A" in conteudo
    assert "Paciente da B" not in conteudo


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_somente_administrador_ve_a_auditoria(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    assert cliente.get(reverse("auditoria:lista")).status_code == 403
    assert "Auditoria" not in cliente.get(reverse("inicio")).content.decode()


def test_admin_do_django_e_somente_leitura(django_user_model, client):
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    client.force_login(root)
    assert client.get(reverse("admin:auditoria_registroauditoria_changelist")).status_code == 200
    assert client.get(reverse("admin:auditoria_registroauditoria_add")).status_code == 403


def test_exclusao_de_usuario_mantem_o_historico(criar_usuario):
    usuario = criar_usuario("temporario")
    usuario.delete()
    assert RegistroAuditoria.objects.filter(objeto_descricao="temporario").exists()


def test_retencao_apaga_so_tentativas_recusadas_antigas():
    antigo = timezone.now() - datetime.timedelta(days=31)
    recente = timezone.now() - datetime.timedelta(days=29)
    for momento in (antigo, recente):
        for acao in (Acao.LOGIN_FALHOU, Acao.LOGIN):
            registro = RegistroAuditoria.objects.create(acao=acao)
            RegistroAuditoria.objects.filter(pk=registro.pk).update(momento=momento)
        tentativa = AccessAttempt.objects.create(username="quem", failures_since_start=1)
        AccessAttempt.objects.filter(pk=tentativa.pk).update(attempt_time=momento)

    call_command("aplicar_retencao")

    restantes = RegistroAuditoria.objects.values_list("acao", "momento")
    assert sorted(acao for acao, _ in restantes) == [Acao.LOGIN, Acao.LOGIN, Acao.LOGIN_FALHOU]
    assert all(m == recente for acao, m in restantes if acao == Acao.LOGIN_FALHOU)
    assert list(AccessAttempt.objects.values_list("attempt_time", flat=True)) == [recente]
