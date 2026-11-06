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


class InvalidFile(ValueError):
    pass


@dataclass
class Transaction:
    fitid: str
    date: datetime.date
    amount: Decimal  # positive = money in, negative = money out
    description: str
    kind: str


@dataclass
class Statement:
    bank_code: str
    account: str
    start: datetime.date | None
    end: datetime.date | None
    balance: Decimal | None
    balance_date: datetime.date | None
    transactions: list
    # Transaction blocks whose date or amount could not be read (reported to the user).
    unreadable_transactions: int = 0


def _text(content: bytes) -> str:
    header = content[:500].decode("ascii", errors="ignore").upper()
    if "CHARSET:1252" in header or "ENCODING:USASCII" in header:
        candidates = ("cp1252", "utf-8")
    else:
        candidates = ("utf-8", "cp1252")
    for encoding in candidates:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _field(block, tag):
    found_match = re.search(rf"<{tag}>([^<\r\n]*)", block, re.IGNORECASE)
    return found_match.group(1).strip() if found_match else ""


def _date(value):
    """OFX dates start with YYYYMMDD (time and time zone may follow)."""
    try:
        return datetime.date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError):
        return None


def _amount(value):
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


def read(content: bytes) -> Statement:
    text = _text(content)
    if "<OFX>" not in text.upper():
        raise InvalidFile(_("O arquivo não é um extrato OFX."))
    transactions = []
    seen = {}
    unreadable_transactions = 0
    for block in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.IGNORECASE | re.DOTALL):
        date = _date(_field(block, "DTPOSTED"))
        amount = _amount(_field(block, "TRNAMT"))
        if date is None or amount is None:
            unreadable_transactions += 1
            continue
        if amount == 0:  # nothing moved (some banks list balance lines this way)
            continue
        memo = _field(block, "MEMO")
        name = _field(block, "NAME")
        description = " · ".join(dict.fromkeys(p for p in (name, memo) if p)) or _field(
            block, "TRNTYPE"
        )
        fitid = (
            _field(block, "FITID")
            or hashlib.sha1(  # noqa: S324 (an id, not security)
                f"{date}|{amount}|{description}".encode()
            ).hexdigest()
        )
        # Some banks repeat a FITID inside the same file: keep both transactions.
        seen[fitid] = seen.get(fitid, 0) + 1
        if seen[fitid] > 1:
            fitid = f"{fitid}#{seen[fitid]}"
        transactions.append(
            Transaction(
                fitid=fitid[:120],
                date=date,
                amount=amount,
                description=description[:200],
                kind=_field(block, "TRNTYPE")[:20],
            )
        )
    balance_block = re.search(r"<LEDGERBAL>(.*?)(</LEDGERBAL>|<AVAILBAL>|$)", text, re.I | re.S)
    balance_text = balance_block.group(1) if balance_block else ""
    return Statement(
        bank_code=_field(text, "BANKID")[:20],
        account=_field(text, "ACCTID")[:40],
        start=_date(_field(text, "DTSTART")),
        end=_date(_field(text, "DTEND")),
        balance=_amount(_field(balance_text, "BALAMT")) if balance_text else None,
        balance_date=_date(_field(balance_text, "DTASOF")) if balance_text else None,
        transactions=transactions,
        unreadable_transactions=unreadable_transactions,
    )
