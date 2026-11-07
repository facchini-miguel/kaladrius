"""Each country's documents, phase 2 of the internationalization (decision 121).

Four roles per country, each one a document or None (then the field is not shown):

- ``paciente``: an individual patient's identity (CPF, NHS number, CURP, DNI...);
- ``funcionario``: an employee's (CPF, Social Security number, National Insurance number...);
- ``pessoa``: an individual as a taxpayer, a supplier or the clinic (CPF, RFC, CUIT, RUC...);
- ``empresa``: a company, as a patient, a supplier or the clinic (CNPJ, EIN, ABN, RFC...).

Values are stored compact (letters and digits, uppercase) in the document fields
(``tax_id``, ``cpf``, ``documento``) and are written each country's way on
screen and on paper. Check digits come from python-stdnum where it has the document; Brazil
keeps its own CPF/CNPJ rules (the alphanumeric CNPJ included). The documents keep their
official names in every language: "CPF" is also "CPF" in English.
"""

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from stdnum import exceptions as stdnum_errors
from stdnum.ar import cuit, dni
from stdnum.au import abn
from stdnum.ca import bn, sin
from stdnum.cl import rut as cl_rut
from stdnum.co import nit
from stdnum.ec import ci as ec_ci
from stdnum.ec import ruc as ec_ruc
from stdnum.gb import nhs
from stdnum.mx import curp, rfc
from stdnum.pe import cui
from stdnum.pe import ruc as pe_ruc
from stdnum.py import ruc as py_ruc
from stdnum.us import ein, ssn
from stdnum.uy import rut as uy_rut
from stdnum.za import idnr

from . import countries
from .validators import valid_cnpj, valid_cpf


class _Invalid(ValueError):
    pass


def _require(condition):
    if not condition:
        raise _Invalid


def _regex(default):
    def validate(value):
        _require(re.fullmatch(default, value))

    return validate


def _thousands(value):
    """1234567 → 1.234.567 (identity numbers in Spanish-speaking countries)."""
    return f"{int(value):,}".replace(",", ".")


@dataclass(frozen=True)
class Document:
    abbreviation: str  # its official name, the same in every language
    example: str  # the field's placeholder, written the country's way
    validate: object  # compact value → raises if invalid
    format_amount: object = None  # compact (and valid) value → as written; None: as stored
    letters: str = ""  # characters kept besides A-Z and 0-9 (Mexico's Ñ and &)

    def normalize(self, value):
        return re.sub(f"[^0-9A-Z{self.letters}]", "", (value or "").upper())

    def is_valid(self, value):
        try:
            self.validate(value)
        except (stdnum_errors.ValidationError, _Invalid, ValueError):
            return False
        return True

    def write(self, value):
        if not (value and self.format_amount and self.is_valid(value)):
            return value or ""
        return self.format_amount(value)


DOCUMENT_ROLES = ("patient", "employee", "person", "company")


@dataclass(frozen=True)
class Documents:
    patient: Document | None
    employee: Document | None
    person: Document | None
    company: Document | None
    # Examples for the practitioner's professional registration (free text).
    professional_registration: str = ""

    def for_role(self, role):
        return getattr(self, role) if role in DOCUMENT_ROLES else None

    def of_roles(self, *roles):
        """The documents of these roles, without repeats or Nones, in order."""
        seen = []
        for role in roles:
            document = self.for_role(role)
            if document is not None and document not in seen:
                seen.append(document)
        return seen

    def label(self, *roles):
        """ "CPF/CNPJ", "RUT", "EIN": the field's name for these roles."""
        return "/".join(dict.fromkeys(d.abbreviation for d in self.of_roles(*roles)))


# ---- Brazil: the system's own rules (apps/core/validators.py).
def _cpf(value):
    _require(value.isdigit() and valid_cpf(value))


def _cnpj(value):
    _require(valid_cnpj(value))


def _write_cpf(v):
    return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"


def _write_cnpj(v):
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"


CPF = Document("CPF", "000.000.000-00", _cpf, _write_cpf)
CNPJ = Document("CNPJ", "00.000.000/0000-00", _cnpj, _write_cnpj)


# ---- Mexico. The RFC's check digit is not checked: many issued RFCs fail it (python-stdnum).
def _rfc(size):
    def validate(value):
        _require(len(value) == size)
        rfc.validate(value)

    return validate


CURP = Document("CURP", "BOXW310820HNERXN09", curp.validate)
RFC_PERSON = Document("RFC", "GODE561231GR8", _rfc(13), letters="Ñ&")
RFC_COMPANY = Document("RFC", "ABC680524P76", _rfc(12), letters="Ñ&")

# ---- Argentina: the DNI identifies people; the CUIT (or CUIL) is the tax number.
DNI_AR = Document("DNI", "12.345.678", dni.validate, dni.format)
CUIT = Document("CUIT", "20-12345678-6", cuit.validate, cuit.format)

# ---- Chile: the RUT (RUN for people) is everybody's number.
RUT_CL = Document("RUT", "12.345.678-5", cl_rut.validate, cl_rut.format)

# ---- Colombia: the cédula de ciudadanía has no check digit; the NIT has one.
CEDULA_CO = Document("Cédula de ciudadanía", "1.234.567.890", _regex(r"\d{3,10}"), _thousands)
NIT_CO = Document("NIT", "213.123.432-1", nit.validate, nit.format)

# ---- Peru.
DNI_PE = Document("DNI", "12345678", cui.validate)
RUC_PE = Document("RUC", "20512333797", pe_ruc.validate)


# ---- Uruguay: the cédula's last digit checks the others (weights 2987634).
def _cedula_uy(value):
    _require(re.fullmatch(r"\d{6,8}", value))
    number = value.zfill(8)
    weighted_sum = sum(int(d) * p for d, p in zip(number[:7], (2, 9, 8, 7, 6, 3, 4), strict=True))
    _require((10 - weighted_sum % 10) % 10 == int(number[7]))


def _write_cedula_uy(v):
    return f"{_thousands(v[:-1])}-{v[-1]}"


CEDULA_UY = Document("Cédula de identidad", "1.234.567-2", _cedula_uy, _write_cedula_uy)
RUT_UY = Document("RUT", "21-100342-001-7", uy_rut.validate, uy_rut.format)

# ---- Paraguay.
CEDULA_PY = Document("Cédula de identidad", "1.234.567", _regex(r"\d{4,9}"), _thousands)
RUC_PY = Document("RUC", "80028061-0", py_ruc.validate, py_ruc.format)

# ---- Bolivia: no public check digit. The cédula may carry a complement and the issuing
# department (1234567 LP, 1234567-1A).
CEDULA_BO = Document("Cédula de identidad", "1234567 LP", _regex(r"\d{4,10}[0-9A-Z]{0,4}"))
NIT_BO = Document("NIT", "1234567012", _regex(r"\d{6,13}"))

# ---- Ecuador.
CEDULA_EC = Document("Cédula", "1710034065", ec_ci.validate)
RUC_EC = Document("RUC", "1792060346001", ec_ruc.validate)

# ---- United States: patients are not asked for a national number (insurance is phase 6).
SSN = Document("SSN", "123-45-6789", ssn.validate, ssn.format)
EIN = Document("EIN", "12-3456789", ein.validate, ein.format)

# ---- United Kingdom. Health services are exempt from VAT, so the business is identified by
# its Companies House number.
NHS = Document("NHS number", "943 476 5919", nhs.validate, nhs.format)
NINO = Document(
    "National Insurance number",
    "AB 12 34 56 C",
    _regex(r"(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\d{6}[A-D]"),
    lambda v: f"{v[:2]} {v[2:4]} {v[4:6]} {v[6:8]} {v[8]}",
)
COMPANY_NUMBER = Document("Company number", "01234567", _regex(r"\d{8}|[A-Z]{2}\d{6}"))


# ---- Canada: each province has its own health card (8 to 12 letters and digits).
def _write_bn(v):
    return f"{v[:9]} {v[9:]}" if len(v) == 15 else v


HEALTH_CARD = Document("Health card number", "1234567890", _regex(r"[A-Z0-9]{8,12}"))
SIN = Document("SIN", "123-456-782", sin.validate, sin.format)
BN = Document("Business Number", "123456782 RT0001", bn.validate, _write_bn)


# ---- Australia: the Medicare card number checks its 9th digit (weights 13791379); the 10th
# is the card's issue number and an 11th the person's position on the card. The tax file
# number is not kept: the law restricts who may record it.
def _medicare(value):
    _require(re.fullmatch(r"[2-6]\d{9,10}", value))
    weighted_sum = sum(int(d) * p for d, p in zip(value[:8], (1, 3, 7, 9, 1, 3, 7, 9), strict=True))
    _require(weighted_sum % 10 == int(value[8]))


def _write_medicare(v):
    return f"{v[:4]} {v[4:9]} {v[9:]}"


MEDICARE = Document("Medicare number", "2123 45670 1", _medicare, _write_medicare)
ABN = Document("ABN", "51 824 753 556", abn.validate, abn.format)

# ---- South Africa: the identity number for people, the CIPC registration for companies.
ID_ZA = Document("ID number", "7503305044089", idnr.validate)
REGISTRATION_ZA = Document(
    "Company registration number",
    "2001/123456/07",
    _regex(r"(18|19|20)\d{2}\d{6}\d{2}"),
    lambda v: f"{v[:4]}/{v[4:10]}/{v[10:]}",
)


DOCUMENTS = {
    "BR": Documents(CPF, CPF, CPF, CNPJ, _("CRO, CRM, CREFITO, CRP…")),
    "MX": Documents(CURP, CURP, RFC_PERSON, RFC_COMPANY, "Cédula profesional"),
    "AR": Documents(DNI_AR, DNI_AR, CUIT, CUIT, "Matrícula nacional (MN) o provincial (MP)"),
    "CL": Documents(RUT_CL, RUT_CL, RUT_CL, RUT_CL, "Registro Nacional de Prestadores"),
    "CO": Documents(CEDULA_CO, CEDULA_CO, NIT_CO, NIT_CO, "ReTHUS, tarjeta profesional"),
    "PE": Documents(DNI_PE, DNI_PE, RUC_PE, RUC_PE, "Colegiatura (COP, CMP…)"),
    "UY": Documents(CEDULA_UY, CEDULA_UY, RUT_UY, RUT_UY, "Registro del MSP"),
    "PY": Documents(CEDULA_PY, CEDULA_PY, RUC_PY, RUC_PY, "Registro profesional (MSPyBS)"),
    "BO": Documents(CEDULA_BO, CEDULA_BO, NIT_BO, NIT_BO, "Matrícula profesional"),
    "EC": Documents(CEDULA_EC, CEDULA_EC, RUC_EC, RUC_EC, "Registro ACESS / SENESCYT"),
    "US": Documents(None, SSN, EIN, EIN, "NPI, state license…"),
    "GB": Documents(NHS, NINO, None, COMPANY_NUMBER, "GDC, GMC, HCPC, NMC…"),
    "CA": Documents(HEALTH_CARD, SIN, BN, BN, "College registration (RCDSO, CPSO…)"),
    "AU": Documents(MEDICARE, None, ABN, ABN, "AHPRA registration number"),
    "ZA": Documents(ID_ZA, ID_ZA, None, REGISTRATION_ZA, "HPCSA registration number"),
}


def for_country(country=None):
    return DOCUMENTS.get(country or countries.clinic_country(), DOCUMENTS[countries.DEFAULT])


def roles(text):
    """ "patient,company" → ("patient", "company"); empty: every role."""
    return tuple(p.strip() for p in (text or "").split(",") if p.strip()) or DOCUMENT_ROLES


def identify(value, roles_=None, country=None):
    """The document of these roles (all of them by default) this value is valid as."""
    for document in for_country(country).of_roles(*(roles_ or DOCUMENT_ROLES)):
        if document.is_valid(value):
            return document
    return None


def write(value, roles_=None, country=None):
    """The stored value written the country's way. In Brazil, as always, by its length."""
    value = value or ""
    if (country or countries.clinic_country()) == "BR":
        if len(value) == 11:
            return _write_cpf(value)
        if len(value) == 14:
            return _write_cnpj(value)
        return value
    document = identify(value, roles_, country)
    return document.write(value) if document else value


def abbreviation(value, roles_=None, country=None):
    """The name of the document this value is ("CNPJ"), or of every one the roles may have
    ("CPF/CNPJ") when it is none of them."""
    document = identify(value, roles_, country) if value else None
    if document is not None:
        return document.abbreviation
    return for_country(country).label(*(roles_ or DOCUMENT_ROLES))


def invalid(label):
    return gettext("%(document)s: invalid number.") % {"document": label}


def clean_value(value, documents, label):
    """Normalize a typed value and check it is one of these documents; ValidationError if not.

    Returns the compact value ("" when empty).
    """
    if not (value or "").strip():
        return ""
    for document in documents:
        compact = document.normalize(value)
        if document.is_valid(compact):
            return compact
    raise ValidationError(invalid(label))
