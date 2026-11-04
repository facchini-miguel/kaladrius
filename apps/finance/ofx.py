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
    date: datetime.date
    amount: Decimal  # positive = money in, negative = money out
    description: str
    kind: str


@dataclass
class Extrato:
    bank_code: str
    account: str
    start: datetime.date | None
    end: datetime.date | None
    balance: Decimal | None
    balance_date: datetime.date | None
    transacoes: list
    # Transaction blocks whose date or amount could not be read (reported to the user).
    unreadable_transactions: int = 0


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


def _data(value):
    """OFX dates start with YYYYMMDD (time and time zone may follow)."""
    try:
        return datetime.date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError):
        return None


def _valor(value):
    value = value.replace(" ", "")
    if "," in value and ("." not in value or value.rfind(",") > value.rfind(".")):
        # Some banks write 1234,56 or even 1.234,56 (the OFX standard has no thousands).
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:  # 1,234.56
        value = value.replace(",", "")
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def ler(conteudo: bytes) -> Extrato:
    texto = _texto(conteudo)
    if "<OFX>" not in texto.upper():
        raise ArquivoInvalido(_("O arquivo não é um extrato OFX."))
    transacoes = []
    vistos = {}
    unreadable_transactions = 0
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, re.IGNORECASE | re.DOTALL):
        date = _data(_campo(bloco, "DTPOSTED"))
        amount = _valor(_campo(bloco, "TRNAMT"))
        if date is None or amount is None:
            unreadable_transactions += 1
            continue
        if amount == 0:  # nothing moved (some banks list balance lines this way)
            continue
        memo = _campo(bloco, "MEMO")
        name = _campo(bloco, "NAME")
        description = " · ".join(dict.fromkeys(p for p in (name, memo) if p)) or _campo(
            bloco, "TRNTYPE"
        )
        fitid = (
            _campo(bloco, "FITID")
            or hashlib.sha1(  # noqa: S324 (an id, not security)
                f"{date}|{amount}|{description}".encode()
            ).hexdigest()
        )
        # Some banks repeat a FITID inside the same file: keep both transactions.
        vistos[fitid] = vistos.get(fitid, 0) + 1
        if vistos[fitid] > 1:
            fitid = f"{fitid}#{vistos[fitid]}"
        transacoes.append(
            Transacao(
                fitid=fitid[:120],
                date=date,
                amount=amount,
                description=description[:200],
                kind=_campo(bloco, "TRNTYPE")[:20],
            )
        )
    saldo_bloco = re.search(r"<LEDGERBAL>(.*?)(</LEDGERBAL>|<AVAILBAL>|$)", texto, re.I | re.S)
    saldo_texto = saldo_bloco.group(1) if saldo_bloco else ""
    return Extrato(
        bank_code=_campo(texto, "BANKID")[:20],
        account=_campo(texto, "ACCTID")[:40],
        start=_data(_campo(texto, "DTSTART")),
        end=_data(_campo(texto, "DTEND")),
        balance=_valor(_campo(saldo_texto, "BALAMT")) if saldo_texto else None,
        balance_date=_data(_campo(saldo_texto, "DTASOF")) if saldo_texto else None,
        transacoes=transacoes,
        unreadable_transactions=unreadable_transactions,
    )
