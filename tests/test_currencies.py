"""The clinic's currency (decision 114): set by the clinic administrator, independent of each
user's language; amounts are shown in it and never converted."""

from decimal import Decimal

import pytest
from django import forms
from django.template import Context, Template
from django.urls import reverse
from django.utils import translation

from apps.core import currencies
from apps.core.forms import CampoDecimal
from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from tests.test_core import dados_clinica

pytestmark = pytest.mark.django_db

VALOR = Decimal("1234.56")


@pytest.mark.parametrize(
    ("codigo", "idioma", "esperado"),
    [
        ("BRL", "pt-br", "R$ 1.234,56"),
        ("BRL", "en", "R$ 1,234.56"),
        ("USD", "en", "US$ 1,234.56"),
        ("USD", "pt-br", "US$ 1.234,56"),
        ("EUR", "es", "1\u00a0234,56 €"),  # after the number with a decimal comma
        ("EUR", "pt-br", "1.234,56 €"),
        ("EUR", "en", "€ 1,234.56"),
        ("MXN", "es", "$ 1\u00a0234,56"),  # Spanish groups with a narrow space
        ("CLP", "es", "$ 1\u00a0235"),  # no cents, rounded
        ("PYG", "en", "₲ 1,235"),
        ("UYU", "es", "$U 1\u00a0234,56"),
    ],
)
def test_simbolo_da_moeda_e_separadores_do_idioma(codigo, idioma, esperado):
    with translation.override(idioma):
        assert currencies.formatar(VALOR, codigo) == esperado


def test_valor_invalido_fica_vazio():
    assert currencies.formatar(None, "USD") == ""
    assert currencies.formatar("abc", "USD") == ""


def test_filtro_usa_a_moeda_da_clinica_atual(clinica_a):
    modelo = Template("{% load formats %}{{ valor|moeda }} {% simbolo_moeda %}")
    contexto = Context({"valor": VALOR})
    with translation.override("pt-br"):
        assert modelo.render(contexto) == "R$ 1.234,56 R$"  # no current clinic: the real
        clinica_a.moeda = "EUR"
        with usar_clinica(clinica_a):
            assert modelo.render(contexto) == "1.234,56 € €"


def test_admin_escolhe_a_moeda_e_valores_aparecem_nela(clinica_a, criar_usuario, cliente_de):
    assert clinica_a.moeda == "BRL"  # existing and new clinics start with the real
    admin = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    assert "Dólar americano (US$, USD)" in admin.get(reverse("clinic_settings")).content.decode()

    resposta = admin.post(reverse("clinic_settings"), dados_clinica(moeda="USD"), follow=True)
    pagina = resposta.content.decode()
    assert "Nenhum valor já lançado foi convertido" in pagina
    clinica_a.refresh_from_db()
    assert clinica_a.moeda == "USD"

    # The language stays each user's own: the currency follows the clinic in any of them.
    admin.post(reverse("change_language"), {"idioma": "es"})
    assert "US$ 0,00" in admin.get(reverse("home")).content.decode()  # received today

    # Saving again without changing it does not repeat the warning.
    admin.post(reverse("change_language"), {"idioma": "pt-br"})
    resposta = admin.post(reverse("clinic_settings"), dados_clinica(moeda="USD"), follow=True)
    assert "Nenhum valor já lançado foi convertido" not in resposta.content.decode()


def test_moeda_desconhecida_e_recusada(clinica_a, criar_usuario, cliente_de):
    admin = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    resposta = admin.post(reverse("clinic_settings"), dados_clinica(moeda="XXX"))
    assert resposta.status_code == 200 and "moeda" in resposta.context["form"].errors


def test_so_o_administrador_muda_a_moeda(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_a", clinica_a, Papel.RECEPCAO))
    assert recepcao.post(reverse("clinic_settings"), dados_clinica(moeda="EUR")).status_code == 403
    clinica_a.refresh_from_db()
    assert clinica_a.moeda == "BRL"


@pytest.mark.parametrize(
    "digitado", ["US$ 1.500,00", "€ 1.500", "1.500 €", "$U 1.500,00", "S/ 1500"]
)
def test_valor_digitado_com_simbolo_de_qualquer_moeda(digitado):
    with translation.override("pt-br"):
        assert CampoDecimal(decimal_places=2, localize=True).clean(digitado) == Decimal("1500.00")


def test_texto_que_nao_e_valor_continua_recusado():
    with translation.override("pt-br"), pytest.raises(forms.ValidationError):
        CampoDecimal(decimal_places=2, localize=True).clean("abc")


def test_formulario_sem_a_moeda_mantem_a_atual(clinica_a, criar_usuario, cliente_de):
    """A settings page opened before the update does not send the currency."""
    clinica_a.moeda = "EUR"
    clinica_a.save(update_fields=["moeda"])
    admin = cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))
    dados = dados_clinica()
    del dados["moeda"]
    assert admin.post(reverse("clinic_settings"), dados).status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.moeda == "EUR"
