"""Each country's documents, phase 2 of the internationalization (decision 121).

Four roles per country, each one a document or None (then the field is not shown):

- ``paciente``: an individual patient's identity (CPF, NHS number, CURP, DNI...);
- ``funcionario``: an employee's (CPF, Social Security number, National Insurance number...);
- ``pessoa``: an individual as a taxpayer, a supplier or the clinic (CPF, RFC, CUIT, RUC...);
- ``empresa``: a company, as a patient, a supplier or the clinic (CNPJ, EIN, ABN, RFC...).

Values are stored compact (letters and digits, uppercase) in the fields that kept their
Brazilian names (``cpf_cnpj``, ``cpf``, ``documento``) and are written each country's way on
screen and on paper. Check digits come from python-stdnum where it has the document; Brazil
keeps its own CPF/CNPJ rules (the alphanumeric CNPJ included). The documents keep their
official names in every language: "CPF" is also "CPF" in English.
"""

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from stdnum import exceptions as stdnum_erros
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
from .validators import cnpj_valido, cpf_valido


class _Invalido(ValueError):
    pass


def _exigir(condicao):
    if not condicao:
        raise _Invalido


def _regex(padrao):
    def validar(valor):
        _exigir(re.fullmatch(padrao, valor))

    return validar


def _milhares(valor):
    """1234567 → 1.234.567 (identity numbers in Spanish-speaking countries)."""
    return f"{int(valor):,}".replace(",", ".")


@dataclass(frozen=True)
class Documento:
    sigla: str  # its official name, the same in every language
    exemplo: str  # the field's placeholder, written the country's way
    validar: object  # compact value → raises if invalid
    formatar: object = None  # compact (and valid) value → as written; None: as stored
    letras: str = ""  # characters kept besides A-Z and 0-9 (Mexico's Ñ and &)

    def normalizar(self, valor):
        return re.sub(f"[^0-9A-Z{self.letras}]", "", (valor or "").upper())

    def valido(self, valor):
        try:
            self.validar(valor)
        except (stdnum_erros.ValidationError, _Invalido, ValueError):
            return False
        return True

    def escrever(self, valor):
        if not (valor and self.formatar and self.valido(valor)):
            return valor or ""
        return self.formatar(valor)


PAPEIS = ("paciente", "funcionario", "pessoa", "empresa")


@dataclass(frozen=True)
class Documentos:
    paciente: Documento | None
    funcionario: Documento | None
    pessoa: Documento | None
    empresa: Documento | None
    # Examples for the practitioner's professional registration (free text).
    registro_profissional: str = ""

    def do_papel(self, papel):
        return getattr(self, papel) if papel in PAPEIS else None

    def de(self, *papeis):
        """The documents of these roles, without repeats or Nones, in order."""
        vistos = []
        for papel in papeis:
            documento = self.do_papel(papel)
            if documento is not None and documento not in vistos:
                vistos.append(documento)
        return vistos

    def rotulo(self, *papeis):
        """ "CPF/CNPJ", "RUT", "EIN": the field's name for these roles."""
        return "/".join(dict.fromkeys(d.sigla for d in self.de(*papeis)))


# ---- Brazil: the system's own rules (apps/core/validators.py).
def _cpf(valor):
    _exigir(valor.isdigit() and cpf_valido(valor))


def _cnpj(valor):
    _exigir(cnpj_valido(valor))


def _escrever_cpf(v):
    return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"


def _escrever_cnpj(v):
    return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"


CPF = Documento("CPF", "000.000.000-00", _cpf, _escrever_cpf)
CNPJ = Documento("CNPJ", "00.000.000/0000-00", _cnpj, _escrever_cnpj)


# ---- Mexico. The RFC's check digit is not checked: many issued RFCs fail it (python-stdnum).
def _rfc(tamanho):
    def validar(valor):
        _exigir(len(valor) == tamanho)
        rfc.validate(valor)

    return validar


CURP = Documento("CURP", "BOXW310820HNERXN09", curp.validate)
RFC_PESSOA = Documento("RFC", "GODE561231GR8", _rfc(13), letras="Ñ&")
RFC_EMPRESA = Documento("RFC", "ABC680524P76", _rfc(12), letras="Ñ&")

# ---- Argentina: the DNI identifies people; the CUIT (or CUIL) is the tax number.
DNI_AR = Documento("DNI", "12.345.678", dni.validate, dni.format)
CUIT = Documento("CUIT", "20-12345678-6", cuit.validate, cuit.format)

# ---- Chile: the RUT (RUN for people) is everybody's number.
RUT_CL = Documento("RUT", "12.345.678-5", cl_rut.validate, cl_rut.format)

# ---- Colombia: the cédula de ciudadanía has no check digit; the NIT has one.
CEDULA_CO = Documento("Cédula de ciudadanía", "1.234.567.890", _regex(r"\d{3,10}"), _milhares)
NIT_CO = Documento("NIT", "213.123.432-1", nit.validate, nit.format)

# ---- Peru.
DNI_PE = Documento("DNI", "12345678", cui.validate)
RUC_PE = Documento("RUC", "20512333797", pe_ruc.validate)


# ---- Uruguay: the cédula's last digit checks the others (weights 2987634).
def _cedula_uy(valor):
    _exigir(re.fullmatch(r"\d{6,8}", valor))
    numero = valor.zfill(8)
    soma = sum(int(d) * p for d, p in zip(numero[:7], (2, 9, 8, 7, 6, 3, 4), strict=True))
    _exigir((10 - soma % 10) % 10 == int(numero[7]))


def _escrever_cedula_uy(v):
    return f"{_milhares(v[:-1])}-{v[-1]}"


CEDULA_UY = Documento("Cédula de identidad", "1.234.567-2", _cedula_uy, _escrever_cedula_uy)
RUT_UY = Documento("RUT", "21-100342-001-7", uy_rut.validate, uy_rut.format)

# ---- Paraguay.
CEDULA_PY = Documento("Cédula de identidad", "1.234.567", _regex(r"\d{4,9}"), _milhares)
RUC_PY = Documento("RUC", "80028061-0", py_ruc.validate, py_ruc.format)

# ---- Bolivia: no public check digit. The cédula may carry a complement and the issuing
# department (1234567 LP, 1234567-1A).
CEDULA_BO = Documento("Cédula de identidad", "1234567 LP", _regex(r"\d{4,10}[0-9A-Z]{0,4}"))
NIT_BO = Documento("NIT", "1234567012", _regex(r"\d{6,13}"))

# ---- Ecuador.
CEDULA_EC = Documento("Cédula", "1710034065", ec_ci.validate)
RUC_EC = Documento("RUC", "1792060346001", ec_ruc.validate)

# ---- United States: patients are not asked for a national number (insurance is phase 6).
SSN = Documento("SSN", "123-45-6789", ssn.validate, ssn.format)
EIN = Documento("EIN", "12-3456789", ein.validate, ein.format)

# ---- United Kingdom. Health services are exempt from VAT, so the business is identified by
# its Companies House number.
NHS = Documento("NHS number", "943 476 5919", nhs.validate, nhs.format)
NINO = Documento(
    "National Insurance number",
    "AB 12 34 56 C",
    _regex(r"(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\d{6}[A-D]"),
    lambda v: f"{v[:2]} {v[2:4]} {v[4:6]} {v[6:8]} {v[8]}",
)
COMPANY_NUMBER = Documento("Company number", "01234567", _regex(r"\d{8}|[A-Z]{2}\d{6}"))


# ---- Canada: each province has its own health card (8 to 12 letters and digits).
def _escrever_bn(v):
    return f"{v[:9]} {v[9:]}" if len(v) == 15 else v


HEALTH_CARD = Documento("Health card number", "1234567890", _regex(r"[A-Z0-9]{8,12}"))
SIN = Documento("SIN", "123-456-782", sin.validate, sin.format)
BN = Documento("Business Number", "123456782 RT0001", bn.validate, _escrever_bn)


# ---- Australia: the Medicare card number checks its 9th digit (weights 13791379); the 10th
# is the card's issue number and an 11th the person's position on the card. The tax file
# number is not kept: the law restricts who may record it.
def _medicare(valor):
    _exigir(re.fullmatch(r"[2-6]\d{9,10}", valor))
    soma = sum(int(d) * p for d, p in zip(valor[:8], (1, 3, 7, 9, 1, 3, 7, 9), strict=True))
    _exigir(soma % 10 == int(valor[8]))


def _escrever_medicare(v):
    return f"{v[:4]} {v[4:9]} {v[9:]}"


MEDICARE = Documento("Medicare number", "2123 45670 1", _medicare, _escrever_medicare)
ABN = Documento("ABN", "51 824 753 556", abn.validate, abn.format)

# ---- South Africa: the identity number for people, the CIPC registration for companies.
ID_ZA = Documento("ID number", "7503305044089", idnr.validate)
REGISTRATION_ZA = Documento(
    "Company registration number",
    "2001/123456/07",
    _regex(r"(18|19|20)\d{2}\d{6}\d{2}"),
    lambda v: f"{v[:4]}/{v[4:10]}/{v[10:]}",
)


DOCUMENTOS = {
    "BR": Documentos(CPF, CPF, CPF, CNPJ, _("CRO, CRM, CREFITO, CRP…")),
    "MX": Documentos(CURP, CURP, RFC_PESSOA, RFC_EMPRESA, "Cédula profesional"),
    "AR": Documentos(DNI_AR, DNI_AR, CUIT, CUIT, "Matrícula nacional (MN) o provincial (MP)"),
    "CL": Documentos(RUT_CL, RUT_CL, RUT_CL, RUT_CL, "Registro Nacional de Prestadores"),
    "CO": Documentos(CEDULA_CO, CEDULA_CO, NIT_CO, NIT_CO, "ReTHUS, tarjeta profesional"),
    "PE": Documentos(DNI_PE, DNI_PE, RUC_PE, RUC_PE, "Colegiatura (COP, CMP…)"),
    "UY": Documentos(CEDULA_UY, CEDULA_UY, RUT_UY, RUT_UY, "Registro del MSP"),
    "PY": Documentos(CEDULA_PY, CEDULA_PY, RUC_PY, RUC_PY, "Registro profesional (MSPyBS)"),
    "BO": Documentos(CEDULA_BO, CEDULA_BO, NIT_BO, NIT_BO, "Matrícula profesional"),
    "EC": Documentos(CEDULA_EC, CEDULA_EC, RUC_EC, RUC_EC, "Registro ACESS / SENESCYT"),
    "US": Documentos(None, SSN, EIN, EIN, "NPI, state license…"),
    "GB": Documentos(NHS, NINO, None, COMPANY_NUMBER, "GDC, GMC, HCPC, NMC…"),
    "CA": Documentos(HEALTH_CARD, SIN, BN, BN, "College registration (RCDSO, CPSO…)"),
    "AU": Documentos(MEDICARE, None, ABN, ABN, "AHPRA registration number"),
    "ZA": Documentos(ID_ZA, ID_ZA, None, REGISTRATION_ZA, "HPCSA registration number"),
}


def do_pais(pais=None):
    return DOCUMENTOS.get(pais or countries.pais_da_clinica(), DOCUMENTOS[countries.PADRAO])


def papeis(texto):
    """ "paciente,empresa" → ("paciente", "empresa"); empty: every role."""
    return tuple(p.strip() for p in (texto or "").split(",") if p.strip()) or PAPEIS


def identificar(valor, papeis_=None, pais=None):
    """The document of these roles (all of them by default) this value is valid as."""
    for documento in do_pais(pais).de(*(papeis_ or PAPEIS)):
        if documento.valido(valor):
            return documento
    return None


def escrever(valor, papeis_=None, pais=None):
    """The stored value written the country's way. In Brazil, as always, by its length."""
    valor = valor or ""
    if (pais or countries.pais_da_clinica()) == "BR":
        if len(valor) == 11:
            return _escrever_cpf(valor)
        if len(valor) == 14:
            return _escrever_cnpj(valor)
        return valor
    documento = identificar(valor, papeis_, pais)
    return documento.escrever(valor) if documento else valor


def sigla(valor, papeis_=None, pais=None):
    """The name of the document this value is ("CNPJ"), or of every one the roles may have
    ("CPF/CNPJ") when it is none of them."""
    documento = identificar(valor, papeis_, pais) if valor else None
    if documento is not None:
        return documento.sigla
    return do_pais(pais).rotulo(*(papeis_ or PAPEIS))


def invalido(rotulo):
    return gettext("%(documento)s: número inválido.") % {"documento": rotulo}


def limpar(valor, documentos, rotulo):
    """Normalize a typed value and check it is one of these documents; ValidationError if not.

    Returns the compact value ("" when empty).
    """
    if not (valor or "").strip():
        return ""
    for documento in documentos:
        compacto = documento.normalizar(valor)
        if documento.valido(compacto):
            return compacto
    raise ValidationError(invalido(rotulo))
