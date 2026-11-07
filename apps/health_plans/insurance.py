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
class CodeFormat:
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
                _("%(nome)s: invalid format. Example: %(exemplo)s.")
                % {"nome": self.name, "exemplo": self.example}
            )
        return code


@dataclass(frozen=True)
class Insurers:
    kinds: str = ""  # the local kinds of plan, as examples for the plan's name
    registration: CodeFormat | None = None  # the insurer's registry
    number: str = ""  # local name of the card number
    group: str = ""  # local name of the group or policy number, where cards have one
    member_code: str = ""  # local name of the patient's code on a family card
    procedure: CodeFormat | None = None  # the procedure coding


INSURERS = {
    "BR": Insurers(
        registration=CodeFormat("ANS", r"\d{6}", "123456"),
        procedure=CodeFormat("TUSS", r"\d{8}", "81000065"),
    ),
    "MX": Insurers("aseguradoras de gastos médicos, planes dentales", number="número de póliza"),
    "AR": Insurers(
        "obras sociales, prepagas, PAMI",
        registration=CodeFormat("RNOS"),
        number="número de afiliado",
        procedure=CodeFormat("nomenclador"),
    ),
    "CL": Insurers("Fonasa, Isapres, seguros dentales", procedure=CodeFormat("Fonasa")),
    "CO": Insurers(
        "EPS, medicina prepagada, pólizas de salud",
        procedure=CodeFormat("CUPS", r"[0-9A-Z]{6}", "232101"),
    ),
    "PE": Insurers("EPS, aseguradoras, SIS, EsSalud", procedure=CodeFormat("CPMS")),
    "UY": Insurers("mutualistas (IAMC), seguros privados"),
    "PY": Insurers("IPS, seguros privados, prepagas"),
    "BO": Insurers("cajas de salud, seguros privados"),
    "EC": Insurers("IESS, seguros privados, medicina prepagada"),
    "US": Insurers(
        "dental insurance carriers (PPO, DHMO), Medicaid",
        registration=CodeFormat("Payer ID", r"[0-9A-Z]{5,10}", "12345"),
        number="Member ID",
        group="Group number",
        procedure=CodeFormat("CDT", r"D\d{4}", "D1110"),
    ),
    "GB": Insurers("NHS, dental plans, private insurance", number="membership number"),
    "CA": Insurers(
        "insurance carriers, Canadian Dental Care Plan (CDCP)",
        number="certificate / ID number",
        group="group / policy number",
        procedure=CodeFormat("USC&LS", r"\d{5}", "11101"),
    ),
    "AU": Insurers(
        "private health funds, Child Dental Benefits Schedule (Medicare)",
        number="membership number",
        member_code="patient number on the card",
        procedure=CodeFormat("ADA item number", r"\d{3}", "114"),
    ),
    "ZA": Insurers(
        "medical aid schemes",
        registration=CodeFormat("CMS"),
        number="membership number",
        member_code="dependant code",
        procedure=CodeFormat("tariff code", r"\d{4}", "8101"),
    ),
}


def for_country(country=None):
    return INSURERS.get(country or countries.clinic_country(), INSURERS[countries.DEFAULT])


def with_local_name(label, local):
    """ "Número da carteirinha (Member ID)"; just the label without a local name."""
    return f"{label} ({local})" if local else str(label)


def registration_label(country=None):
    """ "Registro da operadora (ANS)", or "" where the country has no insurer registry."""
    registration = for_country(country).registration
    return with_local_name(_("Insurer registration"), registration.name) if registration else ""


def code_label(country=None):
    """ "Código (TUSS)", or just "Código" where the country has no single coding."""
    procedure = for_country(country).procedure
    return with_local_name(_("Code"), procedure.name if procedure else "")
