"""Each country's privacy law, record keeping period and tax document (decision 124)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core import legislation
from apps.core.countries import PAISES
from apps.core.isolation import usar_clinica
from apps.finance import services
from apps.finance.models import Entry
from tests.test_finance import HOJE, cenario, entrar, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def test_cada_pais_tem_a_sua_lei():
    assert set(legislation.LEIS) == set(PAISES)
    for country, lei in legislation.LEIS.items():
        assert lei.lei and lei.curta, country
        guarda = lei.guarda
        # A period always names its source; "varies" never comes with a number.
        assert not guarda.anos or guarda.fonte, country
        assert not (guarda.varia and guarda.anos), country
        assert not lei.site or lei.site.startswith("https://"), country


def test_prazo_de_guarda_em_cada_situacao():
    with translation.override("pt-br"):
        assert legislation.prazo_de_guarda("BR") == (
            "O prontuário deve ser guardado por pelo menos 20 anos depois do último registro "
            "(Lei 13.787/2018, art. 6º)."
        )
        assert "até o paciente fazer 21 anos" in legislation.prazo_de_guarda("ZA")
        assert "lei de cada estado" in legislation.prazo_de_guarda("US")
        assert "lei de cada província" in legislation.prazo_de_guarda("CA")
        # No national period confirmed: the source, without a number.
        assert "NTS 139-MINSA/2018/DGAIN" in legislation.prazo_de_guarda("PE")
        assert "Confira com a autoridade" in legislation.prazo_de_guarda("BO")
    with translation.override("es"):
        assert "15" in legislation.prazo_de_guarda("CL")
        assert "O prontuário" not in legislation.prazo_de_guarda("CL")


def test_privacidade_mostra_a_lei_do_pais(client, clinica_a):
    pagina = client.get(reverse("privacy")).content.decode()
    assert "País da clínica" not in pagina  # Brazil: the policy is already Brazilian
    clinica_a.country = "US"
    clinica_a.save()
    pagina = client.get(reverse("privacy")).content.decode()
    assert "País da clínica: Estados Unidos" in pagina and "HIPAA" in pagina
    assert 'href="https://www.hhs.gov/ocr"' in pagina and "lei de cada estado" in pagina


def test_recibo_diz_que_nao_substitui_o_documento_fiscal(cenario, criar_profissional):  # noqa: F811
    clinic = cenario["clinic"]
    dra = criar_profissional(clinic, "Dra. Fictícia", registration="CRO-SP 12345")
    with usar_clinica(clinic):
        entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.RECEBER,
            patient=cenario["patient"],
            description="Limpeza",
            category=cenario["category"],
            practitioner=dra,
            total_amount=Decimal("100"),
            parcelas=1,
            primeiro_vencimento=HOJE,
            user=cenario["admin"],
        )
        payment = services.receber(
            parcelas_de(cenario, entry)[0],
            user=cenario["admin"],
            amount=Decimal("100"),
            method="dinheiro",
            account=cenario["cash_register"],
        )
    admin = entrar(cenario, "admin")
    url = reverse("finance:receipt", args=[payment.pk])
    pagina = admin.get(url).content.decode()
    assert "Dra. Fictícia (CRO-SP 12345)" in pagina
    assert "documento fiscal" not in pagina
    clinic.country = "MX"
    clinic.save()
    pagina = admin.get(url).content.decode()
    assert "Este recibo não substitui o documento fiscal (CFDI)." in pagina


def test_exclusao_cita_a_lei_e_o_prazo_do_pais(cenario):  # noqa: F811
    clinic = cenario["clinic"]
    clinic.country = "CL"
    clinic.save()
    patient = cenario["patient"]
    with usar_clinica(clinic):
        patient.archived = True
        patient.save()
    pagina = entrar(cenario, "admin").get(reverse("patients:delete", args=[patient.pk]))
    text = pagina.content.decode()
    assert "(Ley 19.628)" in text and "15 anos" in text and "LGPD" not in text
