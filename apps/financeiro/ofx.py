"""Reader for bank statement files in OFX (0.20.0, decision 054).

Brazilian banks export OFX 1.x (SGML: leaf tags are not closed, usually in Windows-1252)
or OFX 2.x (XML, usually UTF-8). Both are read with the same tolerant rules, without an
external library: each <STMTTRN> block is one transaction and each leaf tag holds its
value up to the next tag or line break.
"""

import datetime
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext as _


class ArquivoInvalido(ValueError):
    pass


@dataclass
class Transacao:
    fitid: str
    data: datetime.date
    valor: Decimal  # positive = money in, negative = money out
    descricao: str
    tipo: str


@dataclass
class Extrato:
    banco: str
    conta: str
    inicio: datetime.date | None
    fim: datetime.date | None
    saldo: Decimal | None
    saldo_em: datetime.date | None
    transacoes: list


def _texto(conteudo: bytes) -> str:
    cabecalho = conteudo[:500].decode("ascii", errors="ignore").upper()
    if "CHARSET:1252" in cabecalho or "ENCODING:USASCII" in cabecalho:
        candidatos = ("cp1252", "utf-8")
    else:
        candidatos = ("utf-8", "cp1252")
    for codificacao in candidatos:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1")


def _campo(bloco, tag):
    achado = re.search(rf"<{tag}>([^<\r\n]*)", bloco, re.IGNORECASE)
    return achado.group(1).strip() if achado else ""


def _data(valor):
    """OFX dates start with YYYYMMDD (time and time zone may follow)."""
    try:
        return datetime.date(int(valor[0:4]), int(valor[4:6]), int(valor[6:8]))
    except (ValueError, IndexError):
        return None


def _valor(valor):
    valor = valor.replace(" ", "")
    if "," in valor and "." not in valor:  # some banks write 1234,56
        valor = valor.replace(",", ".")
    try:
        return Decimal(valor).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def ler(conteudo: bytes) -> Extrato:
    texto = _texto(conteudo)
    if "<OFX>" not in texto.upper():
        raise ArquivoInvalido(_("O arquivo não é um extrato OFX."))
    transacoes = []
    vistos = {}
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, re.IGNORECASE | re.DOTALL):
        data = _data(_campo(bloco, "DTPOSTED"))
        valor = _valor(_campo(bloco, "TRNAMT"))
        if data is None or valor is None or valor == 0:
            continue
        memo = _campo(bloco, "MEMO")
        nome = _campo(bloco, "NAME")
        descricao = " · ".join(dict.fromkeys(p for p in (nome, memo) if p)) or _campo(
            bloco, "TRNTYPE"
        )
        fitid = (
            _campo(bloco, "FITID")
            or hashlib.sha1(  # noqa: S324 (an id, not security)
                f"{data}|{valor}|{descricao}".encode()
            ).hexdigest()
        )
        # Some banks repeat a FITID inside the same file: keep both transactions.
        vistos[fitid] = vistos.get(fitid, 0) + 1
        if vistos[fitid] > 1:
            fitid = f"{fitid}#{vistos[fitid]}"
        transacoes.append(
            Transacao(
                fitid=fitid[:120],
                data=data,
                valor=valor,
                descricao=descricao[:200],
                tipo=_campo(bloco, "TRNTYPE")[:20],
            )
        )
    saldo_bloco = re.search(r"<LEDGERBAL>(.*?)(</LEDGERBAL>|<AVAILBAL>|$)", texto, re.I | re.S)
    saldo_texto = saldo_bloco.group(1) if saldo_bloco else ""
    return Extrato(
        banco=_campo(texto, "BANKID")[:20],
        conta=_campo(texto, "ACCTID")[:40],
        inicio=_data(_campo(texto, "DTSTART")),
        fim=_data(_campo(texto, "DTEND")),
        saldo=_valor(_campo(saldo_texto, "BALAMT")) if saldo_texto else None,
        saldo_em=_data(_campo(saldo_texto, "DTASOF")) if saldo_texto else None,
        transacoes=transacoes,
    )
