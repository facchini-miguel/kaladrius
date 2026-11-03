"""Each country's privacy law, record keeping period and tax document (decision 124)."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import translation

from apps.core import legislacao
from apps.core.isolamento import usar_clinica
from apps.core.paises import PAISES
from apps.financeiro import servicos
from apps.financeiro.models import Lancamento
from tests.test_finance import HOJE, cenario, entrar, parcelas_de  # noqa: F401

pytestmark = pytest.mark.django_db


def test_cada_pais_tem_a_sua_lei():
    assert set(legislacao.LEIS) == set(PAISES)
    for pais, lei in legislacao.LEIS.items():
        assert lei.lei and lei.curta, pais
        guarda = lei.guarda
        # A period always names its source; "varies" never comes with a number.
        assert not guarda.anos or guarda.fonte, pais
        assert not (guarda.varia and guarda.anos), pais
        assert not lei.site or lei.site.startswith("https://"), pais


def test_prazo_de_guarda_em_cada_situacao():
    with translation.override("pt-br"):
        assert legislacao.prazo_de_guarda("BR") == (
            "O prontuário deve ser guardado por pelo menos 20 anos depois do último registro "
            "(Lei 13.787/2018, art. 6º)."
        )
        assert "até o paciente fazer 21 anos" in legislacao.prazo_de_guarda("ZA")
        assert "lei de cada estado" in legislacao.prazo_de_guarda("US")
        assert "lei de cada província" in legislacao.prazo_de_guarda("CA")
        # No national period confirmed: the source, without a number.
        assert "NTS 139-MINSA/2018/DGAIN" in legislacao.prazo_de_guarda("PE")
        assert "Confira com a autoridade" in legislacao.prazo_de_guarda("BO")
    with translation.override("es"):
        assert "15" in legislacao.prazo_de_guarda("CL")
        assert "O prontuário" not in legislacao.prazo_de_guarda("CL")


def test_privacidade_mostra_a_lei_do_pais(client, clinica_a):
    pagina = client.get(reverse("privacidade")).content.decode()
    assert "País da clínica" not in pagina  # Brazil: the policy is already Brazilian
    clinica_a.pais = "US"
    clinica_a.save()
    pagina = client.get(reverse("privacidade")).content.decode()
    assert "País da clínica: Estados Unidos" in pagina and "HIPAA" in pagina
    assert 'href="https://www.hhs.gov/ocr"' in pagina and "lei de cada estado" in pagina


def test_recibo_diz_que_nao_substitui_o_documento_fiscal(cenario, criar_profissional):  # noqa: F811
    clinica = cenario["clinica"]
    dra = criar_profissional(clinica, "Dra. Fictícia", registro="CRO-SP 12345")
    with usar_clinica(clinica):
        lancamento = servicos.criar_lancamento(
            clinica=clinica,
            tipo=Lancamento.Tipo.RECEBER,
            paciente=cenario["paciente"],
            descricao="Limpeza",
            categoria=cenario["categoria"],
            profissional=dra,
            valor_total=Decimal("100"),
            parcelas=1,
            primeiro_vencimento=HOJE,
            usuario=cenario["admin"],
        )
        pagamento = servicos.receber(
            parcelas_de(cenario, lancamento)[0],
            usuario=cenario["admin"],
            valor=Decimal("100"),
            forma="dinheiro",
            conta=cenario["caixa"],
        )
    admin = entrar(cenario, "admin")
    url = reverse("financeiro:recibo", args=[pagamento.pk])
    pagina = admin.get(url).content.decode()
    assert "Dra. Fictícia (CRO-SP 12345)" in pagina
    assert "documento fiscal" not in pagina
    clinica.pais = "MX"
    clinica.save()
    pagina = admin.get(url).content.decode()
    assert "Este recibo não substitui o documento fiscal (CFDI)." in pagina


def test_exclusao_cita_a_lei_e_o_prazo_do_pais(cenario):  # noqa: F811
    clinica = cenario["clinica"]
    clinica.pais = "CL"
    clinica.save()
    paciente = cenario["paciente"]
    with usar_clinica(clinica):
        paciente.arquivado = True
        paciente.save()
    pagina = entrar(cenario, "admin").get(reverse("pacientes:excluir", args=[paciente.pk]))
    texto = pagina.content.decode()
    assert "(Ley 19.628)" in texto and "15 anos" in texto and "LGPD" not in texto
