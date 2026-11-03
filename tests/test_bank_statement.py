"""Bank statement import (OFX) and reconciliation (0.20.0)."""

import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import conciliacao, ofx, servicos
from apps.financeiro.models import (
    Caixa,
    Categoria,
    Conta,
    ImportacaoExtrato,
    Lancamento,
    MovimentoCaixa,
    TransacaoBancaria,
)
from apps.pacientes.models import Paciente

pytestmark = pytest.mark.django_db
DIA = datetime.date(2026, 10, 5)

# OFX 1.02 (SGML, Windows-1252), as most Brazilian banks export it.
OFX_SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
ENCODING:USASCII
CHARSET:1252

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKACCTFROM><BANKID>341<ACCTID>98765-4<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20261001000000[-3:BRT]<DTEND>20261010000000[-3:BRT]
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261006120000[-3:BRT]<TRNAMT>300.00<FITID>A1
<NAME>JOSÉ PACIENTE<MEMO>PIX RECEBIDO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261007<TRNAMT>-39,90<FITID>A2<MEMO>TARIFA PACOTE</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261008<TRNAMT>500.00<FITID>A3<MEMO>DEPOSITO</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261009<TRNAMT>-120.00<FITID>A4<MEMO>BOLETO</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>1640.10<DTASOF>20261010</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
""".encode("cp1252")

# OFX 2.x (XML, UTF-8), with a repeated FITID and no FITID at all.
OFX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<?OFX OFXHEADER="200" VERSION="211"?>
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20261003</DTPOSTED><TRNAMT>10.00</TRNAMT>
<FITID>X</FITID><MEMO>Pix João</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20261003</DTPOSTED><TRNAMT>10.00</TRNAMT>
<FITID>X</FITID><MEMO>Pix João</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20261004</DTPOSTED><TRNAMT>-5.00</TRNAMT><MEMO>Tarifa</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>OTHER</TRNTYPE><DTPOSTED>20261004</DTPOSTED><TRNAMT>0.00</TRNAMT><FITID>Z</FITID></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
""".encode()


def test_le_ofx_sgml_em_windows_1252():
    extrato = ofx.ler(OFX_SGML)
    assert (extrato.banco, extrato.conta) == ("341", "98765-4")
    assert (extrato.inicio, extrato.fim) == (
        datetime.date(2026, 10, 1),
        datetime.date(2026, 10, 10),
    )
    assert (extrato.saldo, extrato.saldo_em) == (Decimal("1640.10"), datetime.date(2026, 10, 10))
    primeira, segunda = extrato.transacoes[:2]
    assert (primeira.fitid, primeira.data, primeira.valor) == (
        "A1",
        datetime.date(2026, 10, 6),
        Decimal("300.00"),
    )
    assert primeira.descricao == "JOSÉ PACIENTE · PIX RECEBIDO"
    assert segunda.valor == Decimal("-39.90")  # comma as decimal separator


def test_le_ofx_xml_com_fitid_repetido_ou_ausente():
    extrato = ofx.ler(OFX_XML)
    assert [t.descricao for t in extrato.transacoes] == ["Pix João", "Pix João", "Tarifa"]
    fitids = [t.fitid for t in extrato.transacoes]
    assert fitids[:2] == ["X", "X#2"] and len(fitids[2]) == 40  # zero amount skipped
    assert extrato.saldo is None


def test_arquivo_que_nao_e_ofx():
    with pytest.raises(ofx.ArquivoInvalido):
        ofx.ler(b"data;valor\n2026-10-01;10")


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    admin = criar_usuario("admin", clinica_a, Papel.ADMIN)
    with usar_clinica(clinica_a):
        banco = Conta.objects.get(nome="Banco")
        caixa = Conta.objects.get(nome="Caixa")
        paciente = Paciente.objects.create(nome="José Paciente")
        receita = Categoria.objects.get(nome="Tratamento")
        despesa = Categoria.objects.get(nome="Outras despesas")
    return {
        "clinica": clinica_a,
        "banco": banco,
        "caixa": caixa,
        "paciente": paciente,
        "receita": receita,
        "despesa": despesa,
        "admin": admin,
        "cliente": cliente_de(admin),
        "cliente_de": cliente_de,
        "criar_usuario": criar_usuario,
    }


def pago(cenario, valor, data, tipo=Lancamento.Tipo.RECEBER, conta=None):
    with usar_clinica(cenario["clinica"]):
        receber = tipo == Lancamento.Tipo.RECEBER
        lancamento = servicos.criar_lancamento(
            clinica=cenario["clinica"],
            tipo=tipo,
            paciente=cenario["paciente"] if receber else None,
            pessoa="" if receber else "Fornecedor",
            descricao="Tratamento" if receber else "Conta",
            categoria=cenario["receita"] if receber else cenario["despesa"],
            valor_total=Decimal(valor),
            parcelas=1,
            primeiro_vencimento=data,
            usuario=cenario["admin"],
        )
        return servicos.receber(
            lancamento.parcelas.get(),
            usuario=cenario["admin"],
            valor=Decimal(valor),
            forma="pix",
            conta=conta or cenario["banco"],
            data=data,
        )


def importar(cenario, conteudo=OFX_SGML):
    resposta = cenario["cliente"].post(
        reverse("financeiro:extratos"),
        {"conta": cenario["banco"].pk, "arquivo": SimpleUploadedFile("extrato.ofx", conteudo)},
    )
    with usar_clinica(cenario["clinica"]):
        importacao = ImportacaoExtrato.objects.latest("pk")
    assert resposta.url == reverse("financeiro:extrato", args=[importacao.pk])
    return importacao


def transacao(cenario, fitid):
    with usar_clinica(cenario["clinica"]):
        return TransacaoBancaria.objects.get(fitid=fitid)


def test_importar_de_novo_pula_as_repetidas(cenario):
    primeira = importar(cenario)
    segunda = importar(cenario)
    assert (primeira.novas, primeira.repetidas) == (4, 0)
    assert (segunda.novas, segunda.repetidas) == (0, 4)


def test_conciliacao_automatica_so_quando_unica(cenario):
    recebido = pago(cenario, "300.00", DIA)  # A1: one candidate
    pago(cenario, "120.00", DIA, tipo=Lancamento.Tipo.PAGAR)  # A4: two candidates
    pago(cenario, "120.00", DIA + datetime.timedelta(days=1), tipo=Lancamento.Tipo.PAGAR)
    pago(cenario, "500.00", DIA, conta=cenario["caixa"])  # A3: other account, no match
    pago(cenario, "39.90", DIA)  # A2 is money out: a receipt does not match it
    importacao = importar(cenario)
    pagina = cenario["cliente"].get(reverse("financeiro:extrato", args=[importacao.pk]))
    assert pagina.context["unicos"] == 1
    cenario["cliente"].post(reverse("financeiro:extrato_conciliar", args=[importacao.pk]))
    a1, a4 = transacao(cenario, "A1"), transacao(cenario, "A4")
    assert (a1.situacao, a1.pagamento) == (TransacaoBancaria.Situacao.CONCILIADA, recebido)
    assert a4.situacao == TransacaoBancaria.Situacao.PENDENTE
    # The user picks one of the two by hand.
    with usar_clinica(cenario["clinica"]):
        opcoes = conciliacao.candidatos([a4])[a4.pk]
    assert len(opcoes) == 2 and opcoes[0].data == DIA + datetime.timedelta(days=1)  # closest first
    cenario["cliente"].post(
        reverse("financeiro:transacao", args=[a4.pk, "conciliar"]), {"chave": opcoes[1].chave}
    )
    assert transacao(cenario, "A4").pagamento == opcoes[1].objeto
    # A payment already used is no longer offered, and a bogus key is refused.
    resposta = cenario["cliente"].post(
        reverse("financeiro:transacao", args=[transacao(cenario, "A3").pk, "conciliar"]),
        {"chave": f"p{recebido.pk}"},
        follow=True,
    )
    assert "não corresponde" in resposta.content.decode()


def test_deposito_do_caixa_concilia_com_o_movimento(cenario):
    with usar_clinica(cenario["clinica"]):
        caixa = Caixa.objects.create(
            clinica=cenario["clinica"], conta=cenario["caixa"], valor_abertura=Decimal("600")
        )
        movimento = MovimentoCaixa.objects.create(
            clinica=cenario["clinica"],
            caixa=caixa,
            tipo=MovimentoCaixa.Tipo.RETIRADA,
            valor=Decimal("500.00"),
            outra_conta=cenario["banco"],
            motivo="Depósito",
        )
        MovimentoCaixa.objects.filter(pk=movimento.pk).update(
            criado_em=datetime.datetime(2026, 10, 7, 15, tzinfo=datetime.UTC)
        )
    importar(cenario)
    a3 = transacao(cenario, "A3")
    cenario["cliente"].post(
        reverse("financeiro:transacao", args=[a3.pk, "conciliar"]), {"chave": f"m{movimento.pk}"}
    )
    assert transacao(cenario, "A3").movimento == movimento


def test_criar_lancamento_ignorar_e_desfazer(cenario):
    importar(cenario)
    a2 = transacao(cenario, "A2")
    url = reverse("financeiro:transacao_lancamento", args=[a2.pk])
    formulario = cenario["cliente"].get(url).context["form"]
    with usar_clinica(cenario["clinica"]):
        tipos = set(formulario.fields["categoria"].queryset.values_list("tipo", flat=True))
    assert tipos == {Categoria.Tipo.DESPESA}
    cenario["cliente"].post(
        url,
        {
            "descricao": "Tarifa bancária",
            "categoria": cenario["despesa"].pk,
            "pessoa": "Banco Itaú",
            "forma": "transferencia",
        },
    )
    a2 = transacao(cenario, "A2")
    with usar_clinica(cenario["clinica"]):
        lancamento = a2.pagamento.parcela.lancamento
        assert (lancamento.tipo, lancamento.valor_total, lancamento.pessoa) == (
            Lancamento.Tipo.PAGAR,
            Decimal("39.90"),
            "Banco Itaú",
        )
        assert (a2.pagamento.data, a2.pagamento.conta) == (
            datetime.date(2026, 10, 7),
            cenario["banco"],
        )
    a3 = transacao(cenario, "A3")
    ignorar = reverse("financeiro:transacao", args=[a3.pk, "ignorar"])
    cenario["cliente"].post(ignorar, {"motivo": ""})  # a reason is required
    assert transacao(cenario, "A3").situacao == TransacaoBancaria.Situacao.PENDENTE
    cenario["cliente"].post(ignorar, {"motivo": "Transferência entre contas"})
    assert transacao(cenario, "A3").motivo == "Transferência entre contas"
    cenario["cliente"].post(reverse("financeiro:transacao", args=[a3.pk, "desfazer"]))
    a3 = transacao(cenario, "A3")
    assert (a3.situacao, a3.motivo) == (TransacaoBancaria.Situacao.PENDENTE, "")


def test_estorno_volta_a_transacao_para_pendente(cenario):
    recebido = pago(cenario, "300.00", DIA)
    importacao = importar(cenario)
    cenario["cliente"].post(reverse("financeiro:extrato_conciliar", args=[importacao.pk]))
    with usar_clinica(cenario["clinica"]):
        servicos.estornar(recebido, motivo="Devolvido", usuario=cenario["admin"])
    a1 = transacao(cenario, "A1")
    assert (a1.situacao, a1.pagamento) == (TransacaoBancaria.Situacao.PENDENTE, None)


def test_saldo_do_banco_comparado_com_o_sistema(cenario):
    with usar_clinica(cenario["clinica"]):
        Conta.objects.filter(pk=cenario["banco"].pk).update(saldo_inicial=Decimal("1000"))
    pago(cenario, "300.00", DIA)
    importacao = importar(cenario)
    pagina = cenario["cliente"].get(reverse("financeiro:extrato", args=[importacao.pk]))
    assert pagina.context["saldo_sistema"] == Decimal("1300.00")
    assert pagina.context["diferenca"] == Decimal("340.10")


def test_arquivo_invalido_e_permissoes(cenario):
    resposta = cenario["cliente"].post(
        reverse("financeiro:extratos"),
        {"conta": cenario["banco"].pk, "arquivo": SimpleUploadedFile("x.ofx", b"nada")},
    )
    assert "não é um extrato OFX" in resposta.content.decode()
    importacao = importar(cenario)
    recepcao = cenario["cliente_de"](
        cenario["criar_usuario"]("recepcao", cenario["clinica"], Papel.RECEPCAO)
    )
    assert recepcao.get(reverse("financeiro:extratos")).status_code == 403
    assert recepcao.get(reverse("financeiro:extrato", args=[importacao.pk])).status_code == 403


def test_extrato_de_outra_clinica_da_404(cenario, clinica_b):
    importacao = importar(cenario)
    outro = cenario["cliente_de"](cenario["criar_usuario"]("admin_b", clinica_b, Papel.ADMIN))
    assert outro.get(reverse("financeiro:extrato", args=[importacao.pk])).status_code == 404


def test_extrato_ficticio_para_clinica_de_teste(cenario):
    from io import StringIO

    from django.core.management import call_command
    from django.utils import timezone

    recebido = pago(cenario, "250.00", timezone.localdate())
    saida = StringIO()
    call_command("simular_extrato", clinica=cenario["clinica"].nome, stdout=saida)
    extrato = ofx.ler(saida.getvalue().encode())
    assert len(extrato.transacoes) in (4, 5)  # the bank extras, plus the payment (85%)
    assert extrato.saldo is not None
    if len(extrato.transacoes) == 5:
        assert f"P{recebido.pk}" in [t.fitid for t in extrato.transacoes]


def test_linhas_ilegiveis_sao_contadas_e_avisadas(cenario):
    conteudo = OFX_SGML.replace(
        b"</BANKTRANLIST>",
        b"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261009<TRNAMT>1.234,56<FITID>B1</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261009<TRNAMT>2,345.67<FITID>B2</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>2026<TRNAMT>-1.00<FITID>B3</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261009<TRNAMT>abc<FITID>B4</STMTTRN>\n"
        b"</BANKTRANLIST>",
    )
    extrato = ofx.ler(conteudo)
    valores = {t.fitid: t.valor for t in extrato.transacoes}
    assert (valores["B1"], valores["B2"]) == (Decimal("1234.56"), Decimal("2345.67"))
    assert extrato.ignoradas == 2  # bad date, bad amount (zero amounts are not counted)
    resposta = cenario["cliente"].post(
        reverse("financeiro:extratos"),
        {"conta": cenario["banco"].pk, "arquivo": SimpleUploadedFile("extrato.ofx", conteudo)},
        follow=True,
    )
    pagina = resposta.content.decode()
    assert "2 linhas do arquivo não tinham data ou valor legível" in pagina
    with usar_clinica(cenario["clinica"]):
        importacao = ImportacaoExtrato.objects.get()
    assert (importacao.novas, importacao.ignoradas) == (6, 2)
