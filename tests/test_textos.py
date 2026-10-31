"""Texts seen by the front desk review (stage 1): no English left in lists, and Portuguese
month names in lowercase as Portuguese writes them."""

import datetime

import pytest
from django import forms
from django.urls import reverse
from django.utils import translation
from django.utils.formats import date_format

from apps.core.forms import FormularioBootstrap
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_textos", clinica_a, Papel.RECEPCAO))


class _Exemplo(FormularioBootstrap, forms.Form):
    fixa = forms.ChoiceField(choices=[("", "- Select an option -"), ("a", "A")])
    agrupada = forms.ChoiceField(choices=[("Grupo", [("b", "B")])])


def test_opcao_em_branco_das_listas_fixas_vira_traco():
    form = _Exemplo()
    assert form.fields["fixa"].choices == [("", "—"), ("a", "A")]
    assert form.fields["agrupada"].choices == [("Grupo", [("b", "B")])]  # untouched


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
