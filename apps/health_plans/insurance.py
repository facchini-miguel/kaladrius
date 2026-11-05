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
    default: str = ""  # regular expression for the whole code, letters in upper case
    example: str = ""

    def clean_value(self, value):
        """The code without spaces, dots or dashes, in upper case; ValidationError if it does
        not follow the format."""
        code = re.sub(r"[\s.\-/]", "", value or "").upper()
        if code and self.default and not re.fullmatch(self.default, code):
            raise ValidationError(
                _("%(nome)s: formato inválido. Exemplo: %(exemplo)s.")
                % {"nome": self.name, "exemplo": self.example}
            )
        return code


@dataclass(frozen=True)
class Seguros:
    tipos: str = ""  # the local kinds of plan, as examples for the plan's name
    registration: Codigo | None = None  # the insurer's registry
    number: str = ""  # local name of the card number
    group: str = ""  # local name of the group or policy number, where cards have one
    member_code: str = ""  # local name of the patient's code on a family card
    procedure: Codigo | None = None  # the procedure coding


SEGUROS = {
    "BR": Seguros(
        registration=Codigo("ANS", r"\d{6}", "123456"),
        procedure=Codigo("TUSS", r"\d{8}", "81000065"),
    ),
    "MX": Seguros("aseguradoras de gastos médicos, planes dentales", number="número de póliza"),
    "AR": Seguros(
        "obras sociales, prepagas, PAMI",
        registration=Codigo("RNOS"),
        number="número de afiliado",
        procedure=Codigo("nomenclador"),
    ),
    "CL": Seguros("Fonasa, Isapres, seguros dentales", procedure=Codigo("Fonasa")),
    "CO": Seguros(
        "EPS, medicina prepagada, pólizas de salud",
        procedure=Codigo("CUPS", r"[0-9A-Z]{6}", "232101"),
    ),
    "PE": Seguros("EPS, aseguradoras, SIS, EsSalud", procedure=Codigo("CPMS")),
    "UY": Seguros("mutualistas (IAMC), seguros privados"),
    "PY": Seguros("IPS, seguros privados, prepagas"),
    "BO": Seguros("cajas de salud, seguros privados"),
    "EC": Seguros("IESS, seguros privados, medicina prepagada"),
    "US": Seguros(
        "dental insurance carriers (PPO, DHMO), Medicaid",
        registration=Codigo("Payer ID", r"[0-9A-Z]{5,10}", "12345"),
        number="Member ID",
        group="Group number",
        procedure=Codigo("CDT", r"D\d{4}", "D1110"),
    ),
    "GB": Seguros("NHS, dental plans, private insurance", number="membership number"),
    "CA": Seguros(
        "insurance carriers, Canadian Dental Care Plan (CDCP)",
        number="certificate / ID number",
        group="group / policy number",
        procedure=Codigo("USC&LS", r"\d{5}", "11101"),
    ),
    "AU": Seguros(
        "private health funds, Child Dental Benefits Schedule (Medicare)",
        number="membership number",
        member_code="patient number on the card",
        procedure=Codigo("ADA item number", r"\d{3}", "114"),
    ),
    "ZA": Seguros(
        "medical aid schemes",
        registration=Codigo("CMS"),
        number="membership number",
        member_code="dependant code",
        procedure=Codigo("tariff code", r"\d{4}", "8101"),
    ),
}


def for_country(country=None):
    return SEGUROS.get(country or countries.clinic_country(), SEGUROS[countries.DEFAULT])


def com_nome_local(label, local):
    """ "Número da carteirinha (Member ID)"; just the label without a local name."""
    return f"{label} ({local})" if local else str(label)


def rotulo_do_registro(country=None):
    """ "Registro da operadora (ANS)", or "" where the country has no insurer registry."""
    registration = for_country(country).registration
    return com_nome_local(_("Registro da operadora"), registration.name) if registration else ""


def rotulo_do_codigo(country=None):
    """ "Código (TUSS)", or just "Código" where the country has no single coding."""
    procedure = for_country(country).procedure
    return com_nome_local(_("Código"), procedure.name if procedure else "")
