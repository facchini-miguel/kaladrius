import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Clinic
from apps.finance import services
from apps.finance.models import Entry, FinancialAccount, Payment

# Lines a bank shows that the clinic never recorded: (description, amount).
EXTRAS = [
    ("TARIFA PACOTE DE SERVICOS", Decimal("-39.90")),
    ("TARIFA PIX ENVIADO", Decimal("-1.50")),
    ("PIX RECEBIDO - CLIENTE NAO IDENTIFICADO", Decimal("180.00")),
    ("RENDIMENTO APLICACAO AUTOMATICA", Decimal("12.37")),
]


class Command(BaseCommand):
    help = (
        "Prints a FAKE OFX bank statement for a test clinic's account, built from the "
        "payments recorded in it (most of them, a day or two later) plus a few bank fees "
        "and an unrecorded Pix, to try the statement import. Redirect it to a file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic", dest="clinic", required=True, help="Name of the test clinic."
        )
        parser.add_argument(
            "--account", dest="account", default="Banco", help="Account name (default: Banco)."
        )
        parser.add_argument(
            "--days", dest="dias", type=int, default=30, help="Days back (default 30)."
        )

    def handle(self, *args, clinic, account, dias, **options):
        alvo = Clinic.objects.filter(name=clinic).first()
        if alvo is None:
            raise CommandError(f"Clínica “{clinic}” não encontrada.")
        sorteio = random.Random()  # noqa: S311 (fake data, not security)
        hoje = timezone.localdate()
        start = hoje - datetime.timedelta(days=dias)
        with usar_clinica(alvo):
            alvo_conta = FinancialAccount.objects.filter(name=account).first()
            if alvo_conta is None:
                raise CommandError(f"Conta “{account}” não encontrada.")
            linhas = []
            fora = Decimal("0")  # recorded in the system, not in the bank yet
            for p in Payment.objects.filter(
                account=alvo_conta, reversed=False, date__range=(start, hoje)
            ).select_related("installment__entry"):
                entrada = p.installment.entry.kind == Entry.Tipo.RECEBER
                if sorteio.random() < 0.15:
                    fora += p.amount if entrada else -p.amount
                    continue
                date = min(p.date + datetime.timedelta(days=sorteio.choice([0, 0, 1, 2])), hoje)
                description = "PIX RECEBIDO" if entrada else "PAGAMENTO"
                linhas.append((date, p.amount if entrada else -p.amount, description, f"P{p.pk}"))
            for number, (description, amount) in enumerate(EXTRAS):
                date = start + datetime.timedelta(days=sorteio.randint(0, dias))
                linhas.append(
                    (date, amount, description, f"X{alvo_conta.pk}-{date:%Y%m%d}-{number}")
                )
            linhas.sort()
            balance = dict(services.saldos_das_contas(until=hoje)).get(alvo_conta)
        # The bank balance: what the system has plus the extras minus what is not there yet.
        balance = (balance or Decimal("0")) + sum(v for _, v in EXTRAS) - fora
        self.stdout.write(self._ofx(linhas, start, hoje, balance))

    def _ofx(self, linhas, start, end, balance):
        transacoes = "".join(
            "<STMTTRN>\n"
            f"<TRNTYPE>{'CREDIT' if amount > 0 else 'DEBIT'}\n"
            f"<DTPOSTED>{date:%Y%m%d}120000[-3:BRT]\n"
            f"<TRNAMT>{amount}\n"
            f"<FITID>{fitid}\n"
            f"<MEMO>{description}\n"
            "</STMTTRN>\n"
            for date, amount, description, fitid in linhas
        )
        return (
            "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:UTF-8\n"
            "CHARSET:NONE\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
            "<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>BRL\n"
            "<BANKACCTFROM>\n<BANKID>999\n<ACCTID>12345-6\n<ACCTTYPE>CHECKING\n</BANKACCTFROM>\n"
            f"<BANKTRANLIST>\n<DTSTART>{start:%Y%m%d}\n<DTEND>{end:%Y%m%d}\n"
            f"{transacoes}</BANKTRANLIST>\n"
            f"<LEDGERBAL>\n<BALAMT>{balance}\n<DTASOF>{end:%Y%m%d}\n</LEDGERBAL>\n"
            "</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
        )
