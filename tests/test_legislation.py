"""Each country's privacy law, record keeping period and tax document (decision 124)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core import legislation
from apps.core.countries import COUNTRIES
from apps.core.isolation import use_clinic
from apps.finance import services
from apps.finance.models import Entry
from tests.test_finance import HOJE, cenario, entrar, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def test_cada_pais_tem_a_sua_lei():
    assert set(legislation.LAWS) == set(COUNTRIES)
    for country, lei in legislation.LAWS.items():
        assert lei.lei and lei.curta, country
        guarda = lei.guarda
        # A period always names its source; "varies" never comes with a number.
        assert not guarda.anos or guarda.fonte, country
        assert not (guarda.varia and guarda.anos), country
        assert not lei.site or lei.site.startswith("https://"), country


def test_prazo_de_guarda_em_cada_situacao():
    with translation.override("pt-br"):
        assert legislation.retention_period("BR") == (
            "O prontuário deve ser guardado por pelo menos 20 anos depois do último registro "
            "(Lei 13.787/2018, art. 6º)."
        )
        assert "até o paciente fazer 21 anos" in legislation.retention_period("ZA")
        assert "lei de cada estado" in legislation.retention_period("US")
        assert "lei de cada província" in legislation.retention_period("CA")
        # No national period confirmed: the source, without a number.
        assert "NTS 139-MINSA/2018/DGAIN" in legislation.retention_period("PE")
        assert "Confira com a autoridade" in legislation.retention_period("BO")
    with translation.override("es"):
        assert "15" in legislation.retention_period("CL")
        assert "O prontuário" not in legislation.retention_period("CL")


def test_privacidade_mostra_a_lei_do_pais(client, clinica_a):
    page = client.get(reverse("privacy")).content.decode()
    assert "País da clínica" not in page  # Brazil: the policy is already Brazilian
    clinica_a.country = "US"
    clinica_a.save()
    page = client.get(reverse("privacy")).content.decode()
    assert "País da clínica: Estados Unidos" in page and "HIPAA" in page
    assert 'href="https://www.hhs.gov/ocr"' in page and "lei de cada estado" in page


def test_recibo_diz_que_nao_substitui_o_documento_fiscal(cenario, criar_profissional):  # noqa: F811
    clinic = cenario["clinic"]
    dra = criar_profissional(clinic, "Dra. Fictícia", registration="CRO-SP 12345")
    with use_clinic(clinic):
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
    page = admin.get(url).content.decode()
    assert "Dra. Fictícia (CRO-SP 12345)" in page
    assert "documento fiscal" not in page
    clinic.country = "MX"
    clinic.save()
    page = admin.get(url).content.decode()
    assert "Este recibo não substitui o documento fiscal (CFDI)." in page


def test_exclusao_cita_a_lei_e_o_prazo_do_pais(cenario):  # noqa: F811
    clinic = cenario["clinic"]
    clinic.country = "CL"
    clinic.save()
    patient = cenario["patient"]
    with use_clinic(clinic):
        patient.archived = True
        patient.save()
    page = entrar(cenario, "admin").get(reverse("patients:delete", args=[patient.pk]))
    text = page.content.decode()
    assert "(Ley 19.628)" in text and "15 anos" in text and "LGPD" not in text
