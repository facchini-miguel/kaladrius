import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica
from apps.financeiro import servicos
from apps.financeiro.models import Conta, Lancamento, Pagamento

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
        parser.add_argument("--clinica", required=True, help="Name of the test clinic.")
        parser.add_argument("--conta", default="Banco", help="Account name (default: Banco).")
        parser.add_argument("--dias", type=int, default=30, help="Days back (default 30).")

    def handle(self, *args, clinica, conta, dias, **options):
        alvo = Clinica.objects.filter(nome=clinica).first()
        if alvo is None:
            raise CommandError(f"Clínica “{clinica}” não encontrada.")
        sorteio = random.Random()  # noqa: S311 (fake data, not security)
        hoje = timezone.localdate()
        inicio = hoje - datetime.timedelta(days=dias)
        with usar_clinica(alvo):
            alvo_conta = Conta.objects.filter(nome=conta).first()
            if alvo_conta is None:
                raise CommandError(f"Conta “{conta}” não encontrada.")
            linhas = []
            fora = Decimal("0")  # recorded in the system, not in the bank yet
            for p in Pagamento.objects.filter(
                conta=alvo_conta, estornado=False, data__range=(inicio, hoje)
            ).select_related("parcela__lancamento"):
                entrada = p.parcela.lancamento.tipo == Lancamento.Tipo.RECEBER
                if sorteio.random() < 0.15:
                    fora += p.valor if entrada else -p.valor
                    continue
                data = min(p.data + datetime.timedelta(days=sorteio.choice([0, 0, 1, 2])), hoje)
                descricao = "PIX RECEBIDO" if entrada else "PAGAMENTO"
                linhas.append((data, p.valor if entrada else -p.valor, descricao, f"P{p.pk}"))
            for numero, (descricao, valor) in enumerate(EXTRAS):
                data = inicio + datetime.timedelta(days=sorteio.randint(0, dias))
                linhas.append((data, valor, descricao, f"X{alvo_conta.pk}-{data:%Y%m%d}-{numero}"))
            linhas.sort()
            saldo = dict(servicos.saldos_das_contas(ate=hoje)).get(alvo_conta)
        # The bank balance: what the system has plus the extras minus what is not there yet.
        saldo = (saldo or Decimal("0")) + sum(v for _, v in EXTRAS) - fora
        self.stdout.write(self._ofx(linhas, inicio, hoje, saldo))

    def _ofx(self, linhas, inicio, fim, saldo):
        transacoes = "".join(
            "<STMTTRN>\n"
            f"<TRNTYPE>{'CREDIT' if valor > 0 else 'DEBIT'}\n"
            f"<DTPOSTED>{data:%Y%m%d}120000[-3:BRT]\n"
            f"<TRNAMT>{valor}\n"
            f"<FITID>{fitid}\n"
            f"<MEMO>{descricao}\n"
            "</STMTTRN>\n"
            for data, valor, descricao, fitid in linhas
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
