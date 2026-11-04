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
            "--account", dest="conta", default="Banco", help="Account name (default: Banco)."
        )
        parser.add_argument(
            "--days", dest="dias", type=int, default=30, help="Days back (default 30)."
        )

    def handle(self, *args, clinic, conta, dias, **options):
        alvo = Clinic.objects.filter(name=clinic).first()
        if alvo is None:
            raise CommandError(f"Clínica “{clinic}” não encontrada.")
        sorteio = random.Random()  # noqa: S311 (fake data, not security)
        hoje = timezone.localdate()
        inicio = hoje - datetime.timedelta(days=dias)
        with usar_clinica(alvo):
            alvo_conta = FinancialAccount.objects.filter(name=conta).first()
            if alvo_conta is None:
                raise CommandError(f"Conta “{conta}” não encontrada.")
            linhas = []
            fora = Decimal("0")  # recorded in the system, not in the bank yet
            for p in Payment.objects.filter(
                conta=alvo_conta, estornado=False, data__range=(inicio, hoje)
            ).select_related("parcela__entry"):
                entrada = p.parcela.entry.kind == Entry.Tipo.RECEBER
                if sorteio.random() < 0.15:
                    fora += p.amount if entrada else -p.amount
                    continue
                data = min(p.data + datetime.timedelta(days=sorteio.choice([0, 0, 1, 2])), hoje)
                description = "PIX RECEBIDO" if entrada else "PAGAMENTO"
                linhas.append((data, p.amount if entrada else -p.amount, description, f"P{p.pk}"))
            for number, (description, amount) in enumerate(EXTRAS):
                data = inicio + datetime.timedelta(days=sorteio.randint(0, dias))
                linhas.append(
                    (data, amount, description, f"X{alvo_conta.pk}-{data:%Y%m%d}-{number}")
                )
            linhas.sort()
            saldo = dict(services.saldos_das_contas(ate=hoje)).get(alvo_conta)
        # The bank balance: what the system has plus the extras minus what is not there yet.
        saldo = (saldo or Decimal("0")) + sum(v for _, v in EXTRAS) - fora
        self.stdout.write(self._ofx(linhas, inicio, hoje, saldo))

    def _ofx(self, linhas, inicio, fim, saldo):
        transacoes = "".join(
            "<STMTTRN>\n"
            f"<TRNTYPE>{'CREDIT' if amount > 0 else 'DEBIT'}\n"
            f"<DTPOSTED>{data:%Y%m%d}120000[-3:BRT]\n"
            f"<TRNAMT>{amount}\n"
            f"<FITID>{fitid}\n"
            f"<MEMO>{description}\n"
            "</STMTTRN>\n"
            for data, amount, description, fitid in linhas
        )
        return (
            "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:UTF-8\n"
            "CHARSET:NONE\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
            "<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>BRL\n"
            "<BANKACCTFROM>\n<BANKID>999\n<ACCTID>12345-6\n<ACCTTYPE>CHECKING\n</BANKACCTFROM>\n"
            f"<BANKTRANLIST>\n<DTSTART>{inicio:%Y%m%d}\n<DTEND>{fim:%Y%m%d}\n"
            f"{transacoes}</BANKTRANLIST>\n"
            f"<LEDGERBAL>\n<BALAMT>{saldo}\n<DTASOF>{fim:%Y%m%d}\n</LEDGERBAL>\n"
            "</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
        )
