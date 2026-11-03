"""Help menu: user manual for everyone, technical documentation for superusers only."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.ajuda import documentos
from apps.core.models import Papel

pytestmark = pytest.mark.django_db


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))


@pytest.fixture
def superusuario(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("root", password="x-123456789"))
    return client


@pytest.mark.parametrize("pasta", documentos.PASTAS.values())
def test_manual_e_politica_do_site_em_cada_idioma(pasta):
    manual = documentos.DOCS / pasta / "manual"
    paginas = {arquivo.stem for arquivo in manual.glob("*.md")}
    assert {"inicio", "agenda", "pacientes", "privacidade"} <= paginas, pasta


def test_menu_ajuda_abre_o_site_no_idioma_do_usuario(recepcao, settings, django_user_model):
    settings.DOCS_URL = "https://docs.exemplo.test/"
    pagina = recepcao.get(reverse("inicio")).content.decode()
    assert 'href="https://docs.exemplo.test/pt-BR/manual/inicio"' in pagina
    assert 'href="https://docs.exemplo.test/pt-BR/"' in pagina
    usuario = django_user_model.objects.get(username="recepcao")
    usuario.idioma = "en"
    usuario.save()
    pagina = recepcao.get(reverse("inicio")).content.decode()
    assert 'href="https://docs.exemplo.test/manual/inicio"' in pagina


def test_enderecos_antigos_da_ajuda_levam_ao_site(recepcao, settings):
    settings.DOCS_URL = "https://docs.exemplo.test"
    site = "https://docs.exemplo.test/pt-BR/"
    assert recepcao.get(reverse("ajuda:indice")).url == site + "manual/inicio"
    assert recepcao.get(reverse("ajuda:manual", args=["agenda"])).url == site + "manual/agenda"
    assert recepcao.get(reverse("ajuda:tecnica_indice")).url == site
    assert recepcao.get(reverse("ajuda:tecnica", args=["pt-BR/deploy.md"])).url == site
    assert recepcao.get(reverse("ajuda:manual", args=["privacidade"])).url == reverse("privacidade")


def test_lista_logo_depois_de_um_paragrafo_vira_lista():
    texto = "Texto:\n- um\n- dois\n\n```\nlinha:\n- dentro do codigo\n```"
    resultado = documentos._separar_listas(texto)
    assert resultado.startswith("Texto:\n\n- um\n- dois")
    assert "linha:\n- dentro do codigo" in resultado  # code blocks untouched


def test_notas_da_release_do_github_em_ingles():
    saida = StringIO()
    call_command("notas_release", "0.7.0", "--titulo", stdout=saida)
    assert saida.getvalue().strip() == "0.7.0 – Audit log and security (end of phase 1)"
    saida = StringIO()
    call_command("notas_release", "0.7.0", stdout=saida)
    assert saida.getvalue().startswith("- **New · Audit log:** The clinic administrator")
    with pytest.raises(CommandError):
        call_command("notas_release", "9.9.9")


def test_politica_de_privacidade_publica_com_o_contato_da_clinica(client, clinica_a):
    clinica_a.email = "privacidade@sorriso.com.br"
    clinica_a.save()
    login = client.get(reverse("login")).content.decode()
    assert reverse("privacidade") in login
    resposta = client.get(reverse("privacidade"))  # no login: patients do not log in
    pagina = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Política de privacidade" in pagina and "20 anos" in pagina
    assert clinica_a.nome in pagina and "privacidade@sorriso.com.br" in pagina


def test_politica_com_o_contato_da_clinica_da_instalacao(client, clinica_a, recepcao):
    assert recepcao.get(reverse("privacidade")).context["clinica"] == clinica_a
    recepcao.logout()
    assert recepcao.get(reverse("privacidade")).context["clinica"] == clinica_a


def test_politica_sem_clinica_cadastrada(client):
    pagina = client.get(reverse("privacidade"))
    assert pagina.context["clinica"] is None
    assert "Fale com a clínica que atende você." in pagina.content.decode()


@pytest.mark.parametrize(
    ("idioma", "titulo"), [("en", "Privacy policy"), ("es", "Política de privacidad")]
)
def test_politica_nos_tres_idiomas(client, idioma, titulo):
    pagina = client.get(reverse("privacidade"), HTTP_ACCEPT_LANGUAGE=idioma).content.decode()
    assert f"<h1>{titulo}</h1>" in pagina


def test_logo_na_barra_na_entrada_e_na_aba(client, recepcao):
    entrada = client.get(reverse("login")).content.decode()
    assert "logo-entrada" in entrada and "img/favicon" in entrada
    assert "logo-barra" in recepcao.get(reverse("inicio")).content.decode()
    for arquivo in ("logo.svg", "favicon.svg"):
        assert (documentos.DOCS.parent / "static" / "img" / arquivo).is_file()


def test_nome_do_sistema_na_entrada_na_barra_e_na_aba(client, recepcao):
    entrada = client.get(reverse("login")).content.decode()
    assert "<title>Entrar · Kaladrius</title>" in entrada
    assert '<h1 class="h4 mb-4 text-center">Kaladrius</h1>' in entrada
    inicio = recepcao.get(reverse("inicio")).content.decode()
    assert "Kaladrius · versão" in inicio
    for pagina in (entrada, inicio):
        assert "Medical System" not in pagina
