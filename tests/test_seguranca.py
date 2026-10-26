"""Login brute-force protection (django-axes) and the "new version" notice."""

import pytest
from django.urls import reverse

from apps.novidades import releases

pytestmark = pytest.mark.django_db


def tentar(client, senha):
    return client.post(reverse("login"), {"username": "maria", "password": senha})


def test_bloqueia_apos_5_senhas_erradas(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200
    resposta = tentar(client, "errada")
    assert resposta.status_code == 429
    assert "bloqueado temporariamente" in resposta.content.decode()
    # Even the right password is refused while locked out.
    assert tentar(client, "senha-de-teste-123").status_code == 429


def test_login_certo_zera_o_contador(client, criar_usuario):
    criar_usuario("maria")
    for _ in range(4):
        tentar(client, "errada")
    assert tentar(client, "senha-de-teste-123").status_code == 302
    client.post(reverse("logout"))
    for _ in range(4):
        assert tentar(client, "errada").status_code == 200


def test_aviso_de_versao_nova_ate_abrir_as_novidades(client, criar_usuario):
    usuario = criar_usuario("maria")
    client.force_login(usuario)
    assert "Veja o que mudou" in client.get(reverse("inicio")).content.decode()
    client.get(reverse("novidades"))
    usuario.refresh_from_db()
    assert usuario.ultima_versao_vista == releases.versao_atual()
    assert "Veja o que mudou" not in client.get(reverse("inicio")).content.decode()


def test_novidades_filtradas_por_modulo(client, criar_usuario):
    client.force_login(criar_usuario("maria"))
    resposta = client.get(reverse("novidades"), {"modulo": "Agenda"})
    modulos = {item.modulo for _, itens in resposta.context["versoes"] for item in itens}
    assert modulos == {"Agenda"}
    assert "Pacientes" in resposta.context["modulos"]


def test_ip_real_atras_do_proxy(rf):
    from apps.core.middleware import ProxyReversoMiddleware

    request = rf.get("/", HTTP_X_FORWARDED_FOR="2804:abcd::1, 2001:db8::7", REMOTE_ADDR="::1")
    ProxyReversoMiddleware(lambda r: None)(request)
    assert request.META["REMOTE_ADDR"] == "2001:db8::7"
