"""Login protections asked by the owner (decision 111): leaving after 30 idle minutes, a limit
of wrong logins per address, two-step verification with an authenticator app (QR code),
password recovery by e-mail and the eye button on password fields."""

import time

import pyotp
import pytest
from axes.models import AccessAttempt
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.conta import servicos
from apps.conta.models import CodigoRecuperacao, DuasEtapas
from apps.core.models import Papel

pytestmark = pytest.mark.django_db
SENHA = "Senha-Ficticia-2026!"


@pytest.fixture
def pessoa(clinica_a, criar_usuario):
    usuario = criar_usuario("pessoa_conta", clinica_a, Papel.RECEPCAO)
    usuario.set_password(SENHA)
    usuario.email = "pessoa@example.com"
    usuario.save()
    return usuario


def entrar(client, usuario, senha=SENHA, proximo=""):
    dados = {"username": usuario.username, "password": senha}
    if proximo:
        dados["next"] = proximo
    return client.post(reverse("login"), dados)


def ligar_duas_etapas(usuario):
    dispositivo = servicos.preparar(usuario)
    codigos = servicos.ativar(dispositivo)
    return dispositivo, codigos


def codigo_atual(dispositivo, deslocamento=0):
    totp = pyotp.TOTP(dispositivo.segredo)
    return totp.at(time.time() + deslocamento * totp.interval)


# --- Idle time and the eye button ----------------------------------------------------------


def test_sessao_termina_com_30_minutos_sem_uso(client, pessoa):
    assert settings.SESSION_COOKIE_AGE == 30 * 60 and settings.SESSION_SAVE_EVERY_REQUEST
    client.force_login(pessoa)
    pagina = client.get(reverse("inicio")).content.decode()
    assert 'data-inatividade="30"' in pagina and reverse("conta:ativo") in pagina
    assert client.get(reverse("conta:ativo")).status_code == 204
    saiu = client.get(reverse("login"), {"inatividade": "1"})
    assert "30 minutos sem uso" in saiu.content.decode()


def test_ativo_sem_login_vai_para_o_login(client):
    assert client.get(reverse("conta:ativo")).status_code == 302


def test_campos_de_senha_ganham_o_olhinho(client):
    pagina = client.get(reverse("login")).content.decode()
    assert 'data-mostrar-senha="Mostrar a senha"' in pagina


# --- Wrong logins per address ---------------------------------------------------------------


def test_muitas_tentativas_do_mesmo_endereco_bloqueiam_qualquer_usuario(client, pessoa):
    for numero in range(4):  # 4 usernames x 5 failures: 20 from 127.0.0.1
        AccessAttempt.objects.create(
            username=f"tentativa{numero}",
            ip_address="127.0.0.1",
            user_agent="teste",
            failures_since_start=5,
            get_data="",
            post_data="",
            http_accept="",
            path_info="/",
            attempt_time=timezone.now(),
        )
    resposta = entrar(client, pessoa)
    assert resposta.status_code == 200
    assert "Muitas tentativas erradas a partir deste endereço" in resposta.content.decode()
    assert "_auth_user_id" not in client.session


def test_poucas_tentativas_do_endereco_nao_bloqueiam(client, pessoa):
    AccessAttempt.objects.create(
        username="outro",
        ip_address="127.0.0.1",
        user_agent="teste",
        failures_since_start=3,
        get_data="",
        post_data="",
        http_accept="",
        path_info="/",
        attempt_time=timezone.now(),
    )
    assert entrar(client, pessoa).status_code == 302


# --- Two-step verification --------------------------------------------------------------------


def test_ativar_com_qr_code(client, pessoa):
    client.force_login(pessoa)
    pagina = client.get(reverse("conta:duas_etapas")).content.decode()
    assert "<svg" in pagina and "otpauth" not in pagina  # the secret is in the QR, not text
    dispositivo = DuasEtapas.objects.get(usuario=pessoa)
    errado = client.post(reverse("conta:duas_etapas"), {"acao": "ativar", "codigo": "000000"})
    assert "Código incorreto" in errado.content.decode()
    resposta = client.post(
        reverse("conta:duas_etapas"), {"acao": "ativar", "codigo": codigo_atual(dispositivo)}
    )
    texto = resposta.content.decode()
    assert "Verificação em duas etapas ativada" in texto
    assert CodigoRecuperacao.objects.filter(usuario=pessoa).count() == 10
    assert RegistroAuditoria.objects.filter(objeto_descricao__contains="ativada").exists()
    dispositivo.refresh_from_db()
    assert dispositivo.ativa and dispositivo.segredo not in texto


def test_login_pede_o_codigo_depois_da_senha(client, pessoa):
    dispositivo, _ = ligar_duas_etapas(pessoa)
    resposta = entrar(client, pessoa, proximo=reverse("pacientes:lista"))
    assert resposta.url == reverse("conta:codigo")
    assert "_auth_user_id" not in client.session  # not logged in yet
    errado = client.post(reverse("conta:codigo"), {"codigo": "123456"})
    assert "Código incorreto" in errado.content.decode()
    assert AccessAttempt.objects.filter(username=pessoa.username).exists()  # counted
    codigo = codigo_atual(dispositivo)
    certo = client.post(reverse("conta:codigo"), {"codigo": codigo})
    assert certo.url == reverse("pacientes:lista")
    assert client.session["_auth_user_id"] == str(pessoa.pk)
    # The same code does not work twice.
    client.logout()
    entrar(client, pessoa)
    repetido = client.post(reverse("conta:codigo"), {"codigo": codigo})
    assert "Código incorreto" in repetido.content.decode()


def test_codigo_de_recuperacao_vale_uma_vez(client, pessoa):
    _, codigos = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    assert client.post(reverse("conta:codigo"), {"codigo": codigos[0].lower()}).status_code == 302
    client.logout()
    entrar(client, pessoa)
    segunda = client.post(reverse("conta:codigo"), {"codigo": codigos[0]})
    assert "Código incorreto" in segunda.content.decode()


def test_cinco_codigos_errados_voltam_ao_login(client, pessoa):
    ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    for _ in range(5):
        client.post(reverse("conta:codigo"), {"codigo": "000000"})
    # Like 5 wrong passwords: the login protection locks the user for an hour.
    assert client.get(reverse("conta:codigo")).url == reverse("login")
    bloqueado = entrar(client, pessoa)
    assert "_auth_user_id" not in client.session and bloqueado.status_code != 302


def test_passo_do_codigo_expira(client, pessoa):
    dispositivo, _ = ligar_duas_etapas(pessoa)
    entrar(client, pessoa)
    sessao = client.session
    sessao["duas_etapas_pendente"]["momento"] -= 10 * 60
    sessao.save()
    assert client.post(reverse("conta:codigo"), {"codigo": codigo_atual(dispositivo)}).url == (
        reverse("login")
    )


def test_desativar_e_gerar_novos_codigos(client, pessoa):
    dispositivo, antigos = ligar_duas_etapas(pessoa)
    client.force_login(pessoa)
    novos = client.post(
        reverse("conta:duas_etapas"),
        {"acao": "codigos", "codigos-codigo": codigo_atual(dispositivo)},
    )
    assert "Códigos de recuperação" in novos.content.decode()
    assert not servicos.verificar_recuperacao(pessoa, antigos[1])  # old ones stop working
    errado = client.post(
        reverse("conta:duas_etapas"),
        {"acao": "desativar", "desativar-senha": "errada", "desativar-codigo": "000000"},
    )
    assert "Senha incorreta" in errado.content.decode()
    resposta = client.post(
        reverse("conta:duas_etapas"),
        {
            "acao": "desativar",
            "desativar-senha": SENHA,
            "desativar-codigo": codigo_atual(dispositivo, deslocamento=1),
        },
    )
    assert resposta.status_code == 302 and not servicos.ativa_para(pessoa)


def test_administrador_remove_a_verificacao_de_quem_perdeu_o_celular(
    client, clinica_a, pessoa, criar_usuario
):
    ligar_duas_etapas(pessoa)
    admin = criar_usuario("admin_conta", clinica_a, Papel.ADMIN)
    client.force_login(admin)
    vinculo = pessoa.vinculos.get()
    pagina = client.get(reverse("equipe:editar", args=[vinculo.pk])).content.decode()
    assert "Remover a verificação em duas etapas" in pagina
    client.post(reverse("equipe:duas_etapas", args=[vinculo.pk]))
    assert not servicos.ativa_para(pessoa)
    assert RegistroAuditoria.objects.filter(objeto_descricao__contains="removida").exists()


def test_conta_de_demonstracao_nao_ativa(client, pessoa):
    pessoa.demonstracao = True
    pessoa.save(update_fields=["demonstracao"])
    client.force_login(pessoa)
    assert client.get(reverse("conta:duas_etapas")).status_code == 302
    assert not DuasEtapas.objects.exists()


# --- Password recovery by e-mail -------------------------------------------------------------


def test_sem_email_configurado_nao_ha_recuperacao(client, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = False
    assert client.get(reverse("conta:recuperar")).status_code == 404
    assert "Esqueci minha senha" not in client.get(reverse("login")).content.decode()


def test_recuperar_senha_por_email(client, pessoa, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    assert "Esqueci minha senha" in client.get(reverse("login")).content.decode()
    resposta = client.post(reverse("conta:recuperar"), {"email": "pessoa@example.com"})
    assert resposta.url == reverse("conta:recuperar_enviado")
    [mensagem] = mail.outbox
    assert "pessoa_conta" in mensagem.body and "Kaladrius" in mensagem.subject
    link = next(linha for linha in mensagem.body.splitlines() if "/conta/senha/nova/" in linha)
    caminho = link.split("testserver", 1)[1]
    formulario = client.get(caminho, follow=True)
    nova = "Nova-Senha-Ficticia-77"
    client.post(formulario.redirect_chain[-1][0], {"new_password1": nova, "new_password2": nova})
    pessoa.refresh_from_db()
    assert pessoa.check_password(nova)


def test_conta_de_demonstracao_nao_recebe_email(client, pessoa, settings):
    settings.RECUPERAR_SENHA_POR_EMAIL = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    pessoa.demonstracao = True
    pessoa.save(update_fields=["demonstracao"])
    client.post(reverse("conta:recuperar"), {"email": "pessoa@example.com"})
    assert mail.outbox == []
