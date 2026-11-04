"""Health plans and insurance of each country (decision 125), phase 6 of the
internationalization.

The module stays a register (decision 094): no claims, authorizations or billing. What changes
per country is what is registered and how it is called: the insurer's registry (ANS in Brazil,
Payer ID in the United States), the local name of the card number (Member ID, número de
afiliado), the group number of the North American cards, the patient's code on a family card
(South Africa's dependant code, the patient number on Australian fund cards) and the procedure
coding (TUSS, CDT, ADA item numbers, USC&LS, CUPS...). Local names are proper terms and are not
translated: they go in parentheses after the translated field name, as the payment methods do
(decision 123). Codes are typed by the clinic: no code list is shipped (some, like the CDT, are
licensed).
"""

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from apps.core import countries


@dataclass(frozen=True)
class Codigo:
    """A local code: its name and, where it has a fixed format, the pattern and an example."""

    name: str
    padrao: str = ""  # regular expression for the whole code, letters in upper case
    exemplo: str = ""

    def limpar(self, value):
        """The code without spaces, dots or dashes, in upper case; ValidationError if it does
        not follow the format."""
        code = re.sub(r"[\s.\-/]", "", value or "").upper()
        if code and self.padrao and not re.fullmatch(self.padrao, code):
            raise ValidationError(
                _("%(nome)s: formato inválido. Exemplo: %(exemplo)s.")
                % {"nome": self.name, "exemplo": self.exemplo}
            )
        return code


@dataclass(frozen=True)
class Seguros:
    tipos: str = ""  # the local kinds of plan, as examples for the plan's name
    registro: Codigo | None = None  # the insurer's registry
    number: str = ""  # local name of the card number
    grupo: str = ""  # local name of the group or policy number, where cards have one
    beneficiario: str = ""  # local name of the patient's code on a family card
    procedimento: Codigo | None = None  # the procedure coding


SEGUROS = {
    "BR": Seguros(
        registro=Codigo("ANS", r"\d{6}", "123456"),
        procedimento=Codigo("TUSS", r"\d{8}", "81000065"),
    ),
    "MX": Seguros("aseguradoras de gastos médicos, planes dentales", number="número de póliza"),
    "AR": Seguros(
        "obras sociales, prepagas, PAMI",
        registro=Codigo("RNOS"),
        number="número de afiliado",
        procedimento=Codigo("nomenclador"),
    ),
    "CL": Seguros("Fonasa, Isapres, seguros dentales", procedimento=Codigo("Fonasa")),
    "CO": Seguros(
        "EPS, medicina prepagada, pólizas de salud",
        procedimento=Codigo("CUPS", r"[0-9A-Z]{6}", "232101"),
    ),
    "PE": Seguros("EPS, aseguradoras, SIS, EsSalud", procedimento=Codigo("CPMS")),
    "UY": Seguros("mutualistas (IAMC), seguros privados"),
    "PY": Seguros("IPS, seguros privados, prepagas"),
    "BO": Seguros("cajas de salud, seguros privados"),
    "EC": Seguros("IESS, seguros privados, medicina prepagada"),
    "US": Seguros(
        "dental insurance carriers (PPO, DHMO), Medicaid",
        registro=Codigo("Payer ID", r"[0-9A-Z]{5,10}", "12345"),
        number="Member ID",
        grupo="Group number",
        procedimento=Codigo("CDT", r"D\d{4}", "D1110"),
    ),
    "GB": Seguros("NHS, dental plans, private insurance", number="membership number"),
    "CA": Seguros(
        "insurance carriers, Canadian Dental Care Plan (CDCP)",
        number="certificate / ID number",
        grupo="group / policy number",
        procedimento=Codigo("USC&LS", r"\d{5}", "11101"),
    ),
    "AU": Seguros(
        "private health funds, Child Dental Benefits Schedule (Medicare)",
        number="membership number",
        beneficiario="patient number on the card",
        procedimento=Codigo("ADA item number", r"\d{3}", "114"),
    ),
    "ZA": Seguros(
        "medical aid schemes",
        registro=Codigo("CMS"),
        number="membership number",
        beneficiario="dependant code",
        procedimento=Codigo("tariff code", r"\d{4}", "8101"),
    ),
}


def do_pais(pais=None):
    return SEGUROS.get(pais or countries.pais_da_clinica(), SEGUROS[countries.PADRAO])


def com_nome_local(rotulo, local):
    """ "Número da carteirinha (Member ID)"; just the label without a local name."""
    return f"{rotulo} ({local})" if local else str(rotulo)


def rotulo_do_registro(pais=None):
    """ "Registro da operadora (ANS)", or "" where the country has no insurer registry."""
    registro = do_pais(pais).registro
    return com_nome_local(_("Registro da operadora"), registro.name) if registro else ""


def rotulo_do_codigo(pais=None):
    """ "Código (TUSS)", or just "Código" where the country has no single coding."""
    procedimento = do_pais(pais).procedimento
    return com_nome_local(_("Código"), procedimento.name if procedimento else "")
