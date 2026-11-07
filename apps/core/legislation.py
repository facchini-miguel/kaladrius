"""Each country's privacy law, record keeping period and tax document (decision 124), phase 5
of the internationalization.

The privacy policy is written for Brazilian law (LGPD); a clinic in another country sees, above
it, its own law and authority, and how long its health records must be kept. Laws and
authorities are proper names and are not translated. A keeping period is only given where a
national rule sets it; where it depends on the state or province, or no national period was
confirmed, the page says so instead of guessing. The system never deletes a patient with a
medical record (decision 081), whatever the country: these periods are information.

Sources (checked on 2026-11-01): Brazil, Law 13.787/2018, art. 6; Mexico, NOM-004-SSA3-2012,
5.4; Argentina, Law 26.529, art. 18; Chile, Law 20.584, art. 13, and Decree 41/2012, art. 11;
Colombia, Resolution 839 of 2017; South Africa, HPCSA Booklet 9. Mexico's 2025 data protection
law moved the INAI's role to the Secretaría Anticorrupción y Buen Gobierno; Paraguay's Law
7593/2025 applies from November 2027; Chile's Law 21.719 creates the data protection agency.
"""

from dataclasses import dataclass

from django.utils.translation import gettext as _

from . import countries

STATE = "state"
PROVINCE = "province"


@dataclass(frozen=True)
class Retention:
    """How long health records are kept: `years` after the last entry and, for minors, until
    the patient's `until_age` birthday if later; `varies` when each state or province sets it.
    """

    years: int | None = None
    until_age: int | None = None
    source: str = ""
    varies: str = ""


@dataclass(frozen=True)
class Legislation:
    name: str  # the data protection law, in full
    short_name: str  # its short name, for warnings ("LGPD, art. 18")
    authority: str = ""
    site: str = ""
    retention: Retention = Retention()
    tax_document: str = ""  # the tax document a receipt does not replace, where one is required


LAWS = {
    "BR": Legislation(
        "Lei Geral de Proteção de Dados Pessoais (LGPD, Lei 13.709/2018)",
        "LGPD, art. 18",
        "Autoridade Nacional de Proteção de Dados (ANPD)",
        "https://www.gov.br/anpd",
        Retention(20, source="Lei 13.787/2018, art. 6º"),
    ),
    "MX": Legislation(
        "Ley Federal de Protección de Datos Personales en Posesión de los Particulares (2025)",
        "LFPDPPP",
        "Secretaría Anticorrupción y Buen Gobierno",
        retention=Retention(5, source="NOM-004-SSA3-2012"),
        tax_document="CFDI",
    ),
    "AR": Legislation(
        "Ley 25.326 de Protección de los Datos Personales",
        "Ley 25.326",
        "Agencia de Acceso a la Información Pública (AAIP)",
        "https://www.argentina.gob.ar/aaip",
        Retention(10, source="Ley 26.529, art. 18"),
        "factura electrónica (ARCA)",
    ),
    "CL": Legislation(
        "Ley 19.628 sobre Protección de la Vida Privada, reformada por la Ley 21.719",
        "Ley 19.628",
        "Agencia de Protección de Datos Personales (Ley 21.719)",
        retention=Retention(15, source="Ley 20.584, art. 13; Decreto 41/2012"),
        tax_document="boleta o factura electrónica (SII)",
    ),
    "CO": Legislation(
        "Ley 1581 de 2012 de Protección de Datos Personales",
        "Ley 1581 de 2012",
        "Superintendencia de Industria y Comercio (SIC)",
        "https://www.sic.gov.co",
        Retention(15, source="Resolución 839 de 2017"),
        "factura electrónica (DIAN)",
    ),
    "PE": Legislation(
        "Ley 29733 de Protección de Datos Personales",
        "Ley 29733",
        "Autoridad Nacional de Protección de Datos Personales (MINJUSDH)",
        retention=Retention(source="NTS 139-MINSA/2018/DGAIN"),
        tax_document="boleta o factura electrónica (SUNAT)",
    ),
    "UY": Legislation(
        "Ley 18.331 de Protección de Datos Personales",
        "Ley 18.331",
        "Unidad Reguladora y de Control de Datos Personales (URCDP)",
        retention=Retention(source="Decreto 274/010; Decreto 355/982"),
        tax_document="comprobante fiscal electrónico (CFE, DGI)",
    ),
    "PY": Legislation(
        "Ley 7593/2025 de Protección de Datos Personales (aplicable desde noviembre de 2027)",
        "Ley 7593/2025",
        "Agencia Nacional de Protección de Datos Personales (MITIC)",
        tax_document="factura electrónica (SIFEN)",
    ),
    "BO": Legislation(
        "Constitución Política del Estado, arts. 21 y 130 (sin ley general de datos personales)",
        "Constitución, art. 130",
        tax_document="factura (SIN)",
    ),
    "EC": Legislation(
        "Ley Orgánica de Protección de Datos Personales (2021)",
        "LOPDP",
        "Superintendencia de Protección de Datos Personales",
        retention=Retention(source="Acuerdo Ministerial 5216"),
        tax_document="comprobante electrónico (SRI)",
    ),
    "US": Legislation(
        "HIPAA Privacy and Security Rules, and state law",
        "HIPAA",
        "U.S. Department of Health and Human Services, Office for Civil Rights",
        "https://www.hhs.gov/ocr",
        Retention(varies=STATE),
    ),
    "GB": Legislation(
        "UK GDPR and Data Protection Act 2018",
        "UK GDPR",
        "Information Commissioner's Office (ICO)",
        "https://ico.org.uk",
        Retention(source="Records Management Code of Practice"),
    ),
    "CA": Legislation(
        "PIPEDA and provincial health privacy laws (such as PHIPA in Ontario)",
        "PIPEDA",
        "Office of the Privacy Commissioner of Canada",
        "https://www.priv.gc.ca",
        Retention(varies=PROVINCE),
    ),
    "AU": Legislation(
        "Privacy Act 1988 (Australian Privacy Principles)",
        "Privacy Act 1988",
        "Office of the Australian Information Commissioner (OAIC)",
        "https://www.oaic.gov.au",
        Retention(varies=STATE),
    ),
    "ZA": Legislation(
        "Protection of Personal Information Act (POPIA, Act 4 of 2013)",
        "POPIA",
        "Information Regulator",
        "https://inforegulator.org.za",
        Retention(6, 21, source="HPCSA, Booklet 9"),
    ),
}


def for_country(country=None):
    return LAWS.get(country or countries.clinic_country(), LAWS[countries.DEFAULT])


def retention_period(country=None):
    """One sentence on how long the country keeps health records, in the user's language."""
    retention = for_country(country).retention
    if retention.years and retention.until_age:
        return _(
            "Health records must be kept for at least %(years)s years after the last entry "
            "and, for minors, until the patient turns %(age)s, if later (%(source)s)."
        ) % {"years": retention.years, "age": retention.until_age, "source": retention.source}
    if retention.years:
        return _(
            "Health records must be kept for at least %(years)s years after the last entry "
            "(%(source)s)."
        ) % {"years": retention.years, "source": retention.source}
    if retention.varies == STATE:
        return _("How long health records must be kept is set by each state's law.")
    if retention.varies == PROVINCE:
        return _("How long health records must be kept is set by each province's law.")
    if retention.source:
        return _(
            "How long health records must be kept follows %(source)s: check the current period "
            "with the health authority."
        ) % {"source": retention.source}
    return _("Check with the country's health authority how long health records must be kept.")
