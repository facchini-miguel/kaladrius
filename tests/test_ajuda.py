"""Help menu: user manual for everyone, technical documentation for superusers only."""

import re
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


@pytest.mark.parametrize("pasta", ["pt-BR", "en", "es"])
def test_manual_completo_em_cada_idioma(pasta):
    for pagina in documentos.MANUAL:
        assert (documentos.DOCS / pasta / "manual" / f"{pagina}.md").is_file(), (pasta, pagina)


def test_manual_para_toda_a_equipe(recepcao):
    resposta = recepcao.get(reverse("ajuda:indice"), follow=True)
    assert resposta.redirect_chain[-1][0] == reverse("ajuda:manual", args=["inicio"])
    pagina = resposta.content.decode()
    assert "<h1>Primeiros passos</h1>" in pagina
    assert [nome for _slug, nome in resposta.context["paginas"]][:2] == [
        "Primeiros passos",
        "Agenda",
    ]
    assert "<table" in pagina  # Markdown tables rendered
    assert reverse("ajuda:manual", args=["agenda"]) in pagina


def test_manual_no_idioma_do_usuario(recepcao, django_user_model):
    django_user_model.objects.filter(username="recepcao").update(idioma="es")
    pagina = recepcao.get(reverse("ajuda:manual", args=["pacientes"])).content.decode()
    assert "<h1>Pacientes</h1>" in pagina and "Eliminación definitiva" in pagina
    django_user_model.objects.filter(username="recepcao").update(idioma="en")
    pagina = recepcao.get(reverse("ajuda:manual", args=["inicio"])).content.decode()
    assert "<h1>Getting started</h1>" in pagina


def test_lista_logo_depois_de_um_paragrafo_vira_lista():
    texto = "Texto:\n- um\n- dois\n\n```\nlinha:\n- dentro do codigo\n```"
    resultado = documentos._separar_listas(texto)
    assert resultado.startswith("Texto:\n\n- um\n- dois")
    assert "linha:\n- dentro do codigo" in resultado  # code blocks untouched


def test_pagina_inexistente_do_manual(recepcao):
    assert recepcao.get(reverse("ajuda:manual", args=["nao-existe"])).status_code == 404


def test_documentacao_tecnica_so_para_superusuario(recepcao):
    assert recepcao.get(reverse("ajuda:tecnica_indice")).status_code == 404
    url = reverse("ajuda:tecnica", args=["pt-BR/deploy.md"])
    assert recepcao.get(url).status_code == 404
    assert "Documentação técnica" not in recepcao.get(reverse("inicio")).content.decode()


def test_superusuario_le_a_documentacao_tecnica(superusuario):
    resposta = superusuario.get(reverse("ajuda:tecnica_indice"), follow=True)
    assert resposta.redirect_chain[-1][0] == reverse("ajuda:tecnica", args=["pt-BR/README.md"])
    pagina = resposta.content.decode()
    # Links between documents stay inside the system; other files go to GitHub.
    assert reverse("ajuda:tecnica", args=["pt-BR/visao-geral.md"]) in pagina
    assert reverse("ajuda:tecnica", args=["en/README.md"]) in pagina
    assert documentos.REPOSITORIO + "releases.yaml" in pagina
    assert reverse("ajuda:tecnica", args=["pt-BR/decisoes/README.md"]) in pagina


@pytest.mark.parametrize(
    "caminho",
    ["pt-BR/../../README.md", "../config/settings.py", "pt-BR/nao-existe.md", "pt-BR/manual"],
)
def test_documentacao_tecnica_nao_sai_da_pasta_docs(superusuario, caminho):
    assert superusuario.get(reverse("ajuda:tecnica", args=[caminho])).status_code == 404


def test_menu_ajuda(recepcao):
    pagina = recepcao.get(reverse("inicio")).content.decode()
    assert reverse("ajuda:indice") in pagina and reverse("novidades") in pagina


def test_links_entre_documentos_apontam_para_arquivos_existentes():
    """Every relative link in docs/ (three languages) and in the READMEs resolves."""
    raiz = documentos.DOCS.parent
    arquivos = [*documentos.DOCS.rglob("*.md"), *raiz.glob("README*.md")]
    quebrados = []
    for arquivo in arquivos:
        for alvo in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", arquivo.read_text(encoding="utf-8")):
            if alvo.startswith(("http://", "https://", "mailto:")):
                continue
            if not (arquivo.parent / alvo).exists():
                quebrados.append(f"{arquivo.relative_to(raiz)} -> {alvo}")
    assert not quebrados, quebrados


def test_documentacao_tecnica_nos_tres_idiomas():
    """Each technical document has its English and Spanish versions (linked at the top)."""
    for documento in (documentos.DOCS / "pt-BR").rglob("*.md"):
        if "manual" in documento.parts:
            continue
        cabecalho = documento.read_text(encoding="utf-8").split("\n")[2]
        assert "🇺🇸 English" in cabecalho and "🇪🇸 Español" in cabecalho, documento


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


def test_politica_com_varias_clinicas_e_usuario_logado(client, clinica_a, clinica_b, recepcao):
    # Logged in: the user's clinic.
    assert recepcao.get(reverse("privacidade")).context["clinica"] == clinica_a
    assert recepcao.get(reverse("ajuda:manual", args=["privacidade"])).url == reverse("privacidade")
    # Anonymous with two clinics: no way to know which one.
    recepcao.logout()
    pagina = recepcao.get(reverse("privacidade"))
    assert pagina.context["clinica"] is None
    assert "Fale com a clínica que atende você." in pagina.content.decode()


@pytest.mark.parametrize(
    ("idioma", "titulo"), [("en", "Privacy policy"), ("es", "Política de privacidad")]
)
def test_politica_nos_tres_idiomas(client, idioma, titulo):
    pagina = client.get(reverse("privacidade"), HTTP_ACCEPT_LANGUAGE=idioma).content.decode()
    assert f"<h1>{titulo}</h1>" in pagina
