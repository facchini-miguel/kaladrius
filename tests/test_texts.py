"""Texts seen by the front desk review (stage 1): no English left in lists, and Portuguese
month names in lowercase as Portuguese writes them."""

import datetime
from decimal import Decimal

import pytest
from django import forms
from django.urls import reverse
from django.utils import translation
from django.utils.formats import date_format

from apps.core.forms import FormularioBootstrap
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.core.ordem import chave_alfabetica
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_textos", clinica_a, Papel.RECEPCAO))


class _Exemplo(FormularioBootstrap, forms.Form):
    valor = forms.DecimalField(max_digits=12, decimal_places=2, localize=True, required=False)
    fixa = forms.ChoiceField(choices=[("", "- Select an option -"), ("a", "A")])
    agrupada = forms.ChoiceField(choices=[("Grupo", [("b", "B")])])


def test_opcao_em_branco_das_listas_fixas_vira_traco():
    form = _Exemplo()
    assert form.fields["fixa"].choices == [("", "—"), ("a", "A")]
    assert form.fields["agrupada"].choices == [("Grupo", [("b", "B")])]  # untouched


@pytest.mark.parametrize(
    ("idioma", "digitado", "valor"),
    [
        ("pt-br", "1.234.567,89", "1234567.89"),
        ("pt-br", "R$ 1.500,00", "1500.00"),
        ("pt-br", "1.500", "1500"),
        ("pt-br", "1500.50", "1500.50"),
        ("pt-br", "0,5", "0.5"),
        ("es", "12.000,50", "12000.50"),
        ("en", "1,500.00", "1500.00"),
        ("en", "1,500", "1500"),
    ],
)
def test_numeros_com_separador_de_milhar(idioma, digitado, valor):
    with translation.override(idioma):
        form = _Exemplo({"fixa": "a", "agrupada": "b", "valor": digitado})
        assert form.is_valid(), form.errors
    assert form.cleaned_data["valor"] == Decimal(valor)


def test_numero_ambiguo_continua_recusado():
    with translation.override("pt-br"):
        assert not _Exemplo({"fixa": "a", "agrupada": "b", "valor": "1,500"}).is_valid()


def test_formularios_da_recepcao_sem_ingles(clinica_a, recepcao):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Paciente Fictício")
    for url in (
        reverse("pacientes:novo"),
        reverse("pacientes:relacionado_novo", args=[paciente.pk]),
    ):
        pagina = recepcao.get(url).content.decode()
        assert "Select an option" not in pagina, url
        assert '<option value="" selected>—</option>' in pagina, url


def test_meses_em_minuscula_no_portugues():
    dia = datetime.date(2026, 10, 30)
    with translation.override("pt-br"):
        assert date_format(dia, "DATE_FORMAT") == "30 de outubro de 2026"
    with translation.override("es"):
        assert date_format(dia, "DATE_FORMAT") == "30 de octubre de 2026"


def test_lista_de_meses_dos_aniversariantes_comeca_com_maiuscula(recepcao):
    pagina = recepcao.get(reverse("pacientes:aniversariantes"), {"mes": 10}).content.decode()
    assert ">Outubro</option>" in pagina


def test_ordem_alfabetica_com_acentos_e_minusculas(clinica_a):
    """The Alpine database sorted by bytes: "Água" went after "Zeca" (decision 103)."""
    with usar_clinica(clinica_a):
        for nome in ("Zeca Fictício", "Érica Fictícia", "ana Fictícia", "Água Fictícia", "Beto"):
            Paciente.objects.create(nome=nome)
        nomes = list(Paciente.objects.values_list("nome", flat=True))
    assert nomes == ["Água Fictícia", "ana Fictícia", "Beto", "Érica Fictícia", "Zeca Fictício"]


def test_chave_alfabetica_ignora_acento_e_caixa():
    nomes = ["Zeca", "Érica", "ana", "Água", "Beto"]
    assert sorted(nomes, key=chave_alfabetica) == ["Água", "ana", "Beto", "Érica", "Zeca"]


def test_telas_cabem_no_celular(clinica_a, recepcao):
    """Review stage 5 (phone, 390 px): the dental chart scrolls in its own box and the
    printed registration sheet stacks its two columns on a narrow screen."""
    from django.template.loader import render_to_string

    from apps.odontologia.dentes import DENTES_DECIDUOS, DENTES_PERMANENTES

    html = render_to_string(
        "odontologia/_odontograma.html",
        {"permanentes": DENTES_PERMANENTES, "deciduos": DENTES_DECIDUOS, "interativo": True},
    )
    assert 'class="odontograma-rolagem"' in html
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Paciente Fictício")
    ficha = recepcao.get(reverse("pacientes:imprimir", args=[paciente.pk])).content.decode()
    assert 'class="col-12 col-sm-6"' in ficha and 'class="col-6"' not in ficha


def test_painel_do_django_sem_ingles(client, django_user_model):
    """Review (superuser): the admin's action and filter lists showed Django 6.1's
    "- Select an option -" in English."""
    super_usuario = django_user_model.objects.create_superuser("super_textos", "s@example.com", "x")
    client.force_login(super_usuario)
    pagina = client.get(reverse("admin:referencias_uf_changelist")).content.decode()
    assert "Select an option" not in pagina and "Selecione uma opção" in pagina
