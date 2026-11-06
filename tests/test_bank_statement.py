"""Bank statement import (OFX) and reconciliation (0.20.0)."""

import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance import ofx, reconciliation, services
from apps.finance.models import (
    BankTransaction,
    CashMovement,
    CashRegister,
    Category,
    Entry,
    FinancialAccount,
    StatementImport,
)
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db
DAY = datetime.date(2026, 10, 5)

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


def test_reads_ofx_sgml_in_windows_1252():
    statement = ofx.read(OFX_SGML)
    assert (statement.bank_code, statement.account) == ("341", "98765-4")
    assert (statement.start, statement.end) == (
        datetime.date(2026, 10, 1),
        datetime.date(2026, 10, 10),
    )
    assert (statement.balance, statement.balance_date) == (
        Decimal("1640.10"),
        datetime.date(2026, 10, 10),
    )
    first_one, second = statement.transacoes[:2]
    assert (first_one.fitid, first_one.date, first_one.amount) == (
        "A1",
        datetime.date(2026, 10, 6),
        Decimal("300.00"),
    )
    assert first_one.description == "JOSÉ PACIENTE · PIX RECEBIDO"
    assert second.amount == Decimal("-39.90")  # comma as decimal separator


def test_reads_ofx_xml_with_repeated_or_missing_fitid():
    statement = ofx.read(OFX_XML)
    assert [t.description for t in statement.transacoes] == ["Pix João", "Pix João", "Tarifa"]
    fitids = [t.fitid for t in statement.transacoes]
    assert fitids[:2] == ["X", "X#2"] and len(fitids[2]) == 40  # zero amount skipped
    assert statement.balance is None


def test_file_that_is_not_ofx():
    with pytest.raises(ofx.InvalidFile):
        ofx.read(b"data;valor\n2026-10-01;10")


@pytest.fixture
def scenario(clinic_a, create_user, client_for):
    admin = create_user("admin", clinic_a, Role.ADMIN)
    with use_clinic(clinic_a):
        bank = FinancialAccount.objects.get(name="Banco")
        cash_register = FinancialAccount.objects.get(name="Caixa")
        patient = Patient.objects.create(name="José Paciente")
        income = Category.objects.get(name="Tratamento")
        expense = Category.objects.get(name="Outras despesas")
    return {
        "clinic": clinic_a,
        "bank": bank,
        "cash_register": cash_register,
        "patient": patient,
        "income": income,
        "expense": expense,
        "admin": admin,
        "client": client_for(admin),
        "client_for": client_for,
        "create_user": create_user,
    }


def paid(scenario, amount, date, kind=Entry.Kind.RECEIVABLE, account=None):
    with use_clinic(scenario["clinic"]):
        receive = kind == Entry.Kind.RECEIVABLE
        entry = services.create_entry(
            clinic=scenario["clinic"],
            kind=kind,
            patient=scenario["patient"] if receive else None,
            payer="" if receive else "Fornecedor",
            description="Tratamento" if receive else "Conta",
            category=scenario["income"] if receive else scenario["expense"],
            total_amount=Decimal(amount),
            parcelas=1,
            primeiro_vencimento=date,
            user=scenario["admin"],
        )
        return services.receive(
            entry.installments.get(),
            user=scenario["admin"],
            amount=Decimal(amount),
            method="pix",
            account=account or scenario["bank"],
            date=date,
        )


def import_statement(scenario, content=OFX_SGML):
    response = scenario["client"].post(
        reverse("finance:statements"),
        {"account": scenario["bank"].pk, "file": SimpleUploadedFile("extrato.ofx", content)},
    )
    with use_clinic(scenario["clinic"]):
        statement_import = StatementImport.objects.latest("pk")
    assert response.url == reverse("finance:statement", args=[statement_import.pk])
    return statement_import


def transaction(scenario, fitid):
    with use_clinic(scenario["clinic"]):
        return BankTransaction.objects.get(fitid=fitid)


def test_importing_again_skips_repeated(scenario):
    first_one = import_statement(scenario)
    second = import_statement(scenario)
    assert (first_one.new_transactions, first_one.duplicate_transactions) == (4, 0)
    assert (second.new_transactions, second.duplicate_transactions) == (0, 4)


def test_automatic_reconciliation_only_when_unique(scenario):
    received_amount = paid(scenario, "300.00", DAY)  # A1: one candidate
    paid(scenario, "120.00", DAY, kind=Entry.Kind.PAYABLE)  # A4: two candidates
    paid(scenario, "120.00", DAY + datetime.timedelta(days=1), kind=Entry.Kind.PAYABLE)
    paid(scenario, "500.00", DAY, account=scenario["cash_register"])  # A3: other account, no match
    paid(scenario, "39.90", DAY)  # A2 is money out: a receipt does not match it
    statement_import = import_statement(scenario)
    page = scenario["client"].get(reverse("finance:statement", args=[statement_import.pk]))
    assert page.context["unique"] == 1
    scenario["client"].post(reverse("finance:statement_reconcile", args=[statement_import.pk]))
    a1, a4 = transaction(scenario, "A1"), transaction(scenario, "A4")
    assert (a1.status, a1.payment) == (BankTransaction.Status.RECONCILED, received_amount)
    assert a4.status == BankTransaction.Status.PENDING
    # The user picks one of the two by hand.
    with use_clinic(scenario["clinic"]):
        options = reconciliation.candidates([a4])[a4.pk]
    assert len(options) == 2 and options[0].date == DAY + datetime.timedelta(
        days=1
    )  # closest first
    scenario["client"].post(
        reverse("finance:transaction", args=[a4.pk, "reconcile"]), {"key": options[1].key}
    )
    assert transaction(scenario, "A4").payment == options[1].obj
    # A payment already used is no longer offered, and a bogus key is refused.
    response = scenario["client"].post(
        reverse("finance:transaction", args=[transaction(scenario, "A3").pk, "reconcile"]),
        {"key": f"p{received_amount.pk}"},
        follow=True,
    )
    assert "não corresponde" in response.content.decode()


def test_cash_deposit_reconciles_with_the_movement(scenario):
    with use_clinic(scenario["clinic"]):
        cash_register = CashRegister.objects.create(
            clinic=scenario["clinic"],
            account=scenario["cash_register"],
            opening_amount=Decimal("600"),
        )
        cash_movement = CashMovement.objects.create(
            clinic=scenario["clinic"],
            cash_register=cash_register,
            kind=CashMovement.Kind.WITHDRAWAL,
            amount=Decimal("500.00"),
            other_account=scenario["bank"],
            reason="Depósito",
        )
        CashMovement.objects.filter(pk=cash_movement.pk).update(
            created_at=datetime.datetime(2026, 10, 7, 15, tzinfo=datetime.UTC)
        )
    import_statement(scenario)
    a3 = transaction(scenario, "A3")
    scenario["client"].post(
        reverse("finance:transaction", args=[a3.pk, "reconcile"]), {"key": f"m{cash_movement.pk}"}
    )
    assert transaction(scenario, "A3").cash_movement == cash_movement


def test_create_entry_ignore_and_undo(scenario):
    import_statement(scenario)
    a2 = transaction(scenario, "A2")
    url = reverse("finance:transaction_entry", args=[a2.pk])
    form_page = scenario["client"].get(url).context["form"]
    with use_clinic(scenario["clinic"]):
        kinds = set(form_page.fields["category"].queryset.values_list("kind", flat=True))
    assert kinds == {Category.Kind.EXPENSE}
    scenario["client"].post(
        url,
        {
            "description": "Tarifa bancária",
            "category": scenario["expense"].pk,
            "payer": "Banco Itaú",
            "method": "transferencia",
        },
    )
    a2 = transaction(scenario, "A2")
    with use_clinic(scenario["clinic"]):
        entry = a2.payment.installment.entry
        assert (entry.kind, entry.total_amount, entry.payer) == (
            Entry.Kind.PAYABLE,
            Decimal("39.90"),
            "Banco Itaú",
        )
        assert (a2.payment.date, a2.payment.account) == (
            datetime.date(2026, 10, 7),
            scenario["bank"],
        )
    a3 = transaction(scenario, "A3")
    ignore = reverse("finance:transaction", args=[a3.pk, "ignore"])
    scenario["client"].post(ignore, {"reason": ""})  # a reason is required
    assert transaction(scenario, "A3").status == BankTransaction.Status.PENDING
    scenario["client"].post(ignore, {"reason": "Transferência entre contas"})
    assert transaction(scenario, "A3").reason == "Transferência entre contas"
    scenario["client"].post(reverse("finance:transaction", args=[a3.pk, "undo"]))
    a3 = transaction(scenario, "A3")
    assert (a3.status, a3.reason) == (BankTransaction.Status.PENDING, "")


def test_reversal_returns_transaction_to_pending(scenario):
    received_amount = paid(scenario, "300.00", DAY)
    statement_import = import_statement(scenario)
    scenario["client"].post(reverse("finance:statement_reconcile", args=[statement_import.pk]))
    with use_clinic(scenario["clinic"]):
        services.reverse_payment(received_amount, reason="Devolvido", user=scenario["admin"])
    a1 = transaction(scenario, "A1")
    assert (a1.status, a1.payment) == (BankTransaction.Status.PENDING, None)


def test_bank_balance_compared_with_the_system(scenario):
    with use_clinic(scenario["clinic"]):
        FinancialAccount.objects.filter(pk=scenario["bank"].pk).update(
            opening_balance=Decimal("1000")
        )
    paid(scenario, "300.00", DAY)
    statement_import = import_statement(scenario)
    page = scenario["client"].get(reverse("finance:statement", args=[statement_import.pk]))
    assert page.context["system_balance"] == Decimal("1300.00")
    assert page.context["difference"] == Decimal("340.10")


def test_invalid_file_and_permissions(scenario):
    response = scenario["client"].post(
        reverse("finance:statements"),
        {"account": scenario["bank"].pk, "file": SimpleUploadedFile("x.ofx", b"nada")},
    )
    assert "não é um extrato OFX" in response.content.decode()
    statement_import = import_statement(scenario)
    reception = scenario["client_for"](
        scenario["create_user"]("recepcao", scenario["clinic"], Role.FRONT_DESK)
    )
    assert reception.get(reverse("finance:statements")).status_code == 403
    assert (
        reception.get(reverse("finance:statement", args=[statement_import.pk])).status_code == 403
    )


def test_statement_of_another_clinic_gives_404(scenario, clinic_b):
    statement_import = import_statement(scenario)
    other = scenario["client_for"](scenario["create_user"]("admin_b", clinic_b, Role.ADMIN))
    assert other.get(reverse("finance:statement", args=[statement_import.pk])).status_code == 404


def test_fake_statement_for_test_clinic(scenario):
    from io import StringIO

    from django.core.management import call_command
    from django.utils import timezone

    received_amount = paid(scenario, "250.00", timezone.localdate())
    output = StringIO()
    call_command("simulate_statement", clinic=scenario["clinic"].name, stdout=output)
    statement = ofx.read(output.getvalue().encode())
    assert len(statement.transacoes) in (4, 5)  # the bank extras, plus the payment (85%)
    assert statement.balance is not None
    if len(statement.transacoes) == 5:
        assert f"P{received_amount.pk}" in [t.fitid for t in statement.transacoes]


def test_unreadable_lines_are_counted_and_reported(scenario):
    content = OFX_SGML.replace(
        b"</BANKTRANLIST>",
        b"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261009<TRNAMT>1.234,56<FITID>B1</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261009<TRNAMT>2,345.67<FITID>B2</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>2026<TRNAMT>-1.00<FITID>B3</STMTTRN>\n"
        b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261009<TRNAMT>abc<FITID>B4</STMTTRN>\n"
        b"</BANKTRANLIST>",
    )
    statement = ofx.read(content)
    paid_and_balance = {t.fitid: t.amount for t in statement.transacoes}
    assert (paid_and_balance["B1"], paid_and_balance["B2"]) == (
        Decimal("1234.56"),
        Decimal("2345.67"),
    )
    assert (
        statement.unreadable_transactions == 2
    )  # bad date, bad amount (zero amounts are not counted)
    response = scenario["client"].post(
        reverse("finance:statements"),
        {"account": scenario["bank"].pk, "file": SimpleUploadedFile("extrato.ofx", content)},
        follow=True,
    )
    page = response.content.decode()
    assert "2 linhas do arquivo não tinham data ou valor legível" in page
    with use_clinic(scenario["clinic"]):
        statement_import = StatementImport.objects.get()
    assert (statement_import.new_transactions, statement_import.unreadable_transactions) == (6, 2)
