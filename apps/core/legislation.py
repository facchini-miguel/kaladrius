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

ESTADO = "estado"
PROVINCIA = "provincia"


@dataclass(frozen=True)
class Guarda:
    """How long health records are kept: `anos` after the last entry and, for minors, until
    the patient's `ate_idade` birthday if later; `varia` when each state or province sets it.
    """

    anos: int | None = None
    ate_idade: int | None = None
    fonte: str = ""
    varia: str = ""


@dataclass(frozen=True)
class Legislacao:
    lei: str  # the data protection law, in full
    curta: str  # its short name, for warnings ("LGPD, art. 18")
    autoridade: str = ""
    site: str = ""
    guarda: Guarda = Guarda()
    fiscal: str = ""  # the tax document a receipt does not replace, where one is required


LEIS = {
    "BR": Legislacao(
        "Lei Geral de Proteção de Dados Pessoais (LGPD, Lei 13.709/2018)",
        "LGPD, art. 18",
        "Autoridade Nacional de Proteção de Dados (ANPD)",
        "https://www.gov.br/anpd",
        Guarda(20, fonte="Lei 13.787/2018, art. 6º"),
    ),
    "MX": Legislacao(
        "Ley Federal de Protección de Datos Personales en Posesión de los Particulares (2025)",
        "LFPDPPP",
        "Secretaría Anticorrupción y Buen Gobierno",
        guarda=Guarda(5, fonte="NOM-004-SSA3-2012"),
        fiscal="CFDI",
    ),
    "AR": Legislacao(
        "Ley 25.326 de Protección de los Datos Personales",
        "Ley 25.326",
        "Agencia de Acceso a la Información Pública (AAIP)",
        "https://www.argentina.gob.ar/aaip",
        Guarda(10, fonte="Ley 26.529, art. 18"),
        "factura electrónica (ARCA)",
    ),
    "CL": Legislacao(
        "Ley 19.628 sobre Protección de la Vida Privada, reformada por la Ley 21.719",
        "Ley 19.628",
        "Agencia de Protección de Datos Personales (Ley 21.719)",
        guarda=Guarda(15, fonte="Ley 20.584, art. 13; Decreto 41/2012"),
        fiscal="boleta o factura electrónica (SII)",
    ),
    "CO": Legislacao(
        "Ley 1581 de 2012 de Protección de Datos Personales",
        "Ley 1581 de 2012",
        "Superintendencia de Industria y Comercio (SIC)",
        "https://www.sic.gov.co",
        Guarda(15, fonte="Resolución 839 de 2017"),
        "factura electrónica (DIAN)",
    ),
    "PE": Legislacao(
        "Ley 29733 de Protección de Datos Personales",
        "Ley 29733",
        "Autoridad Nacional de Protección de Datos Personales (MINJUSDH)",
        guarda=Guarda(fonte="NTS 139-MINSA/2018/DGAIN"),
        fiscal="boleta o factura electrónica (SUNAT)",
    ),
    "UY": Legislacao(
        "Ley 18.331 de Protección de Datos Personales",
        "Ley 18.331",
        "Unidad Reguladora y de Control de Datos Personales (URCDP)",
        guarda=Guarda(fonte="Decreto 274/010; Decreto 355/982"),
        fiscal="comprobante fiscal electrónico (CFE, DGI)",
    ),
    "PY": Legislacao(
        "Ley 7593/2025 de Protección de Datos Personales (aplicable desde noviembre de 2027)",
        "Ley 7593/2025",
        "Agencia Nacional de Protección de Datos Personales (MITIC)",
        fiscal="factura electrónica (SIFEN)",
    ),
    "BO": Legislacao(
        "Constitución Política del Estado, arts. 21 y 130 (sin ley general de datos personales)",
        "Constitución, art. 130",
        fiscal="factura (SIN)",
    ),
    "EC": Legislacao(
        "Ley Orgánica de Protección de Datos Personales (2021)",
        "LOPDP",
        "Superintendencia de Protección de Datos Personales",
        guarda=Guarda(fonte="Acuerdo Ministerial 5216"),
        fiscal="comprobante electrónico (SRI)",
    ),
    "US": Legislacao(
        "HIPAA Privacy and Security Rules, and state law",
        "HIPAA",
        "U.S. Department of Health and Human Services, Office for Civil Rights",
        "https://www.hhs.gov/ocr",
        Guarda(varia=ESTADO),
    ),
    "GB": Legislacao(
        "UK GDPR and Data Protection Act 2018",
        "UK GDPR",
        "Information Commissioner's Office (ICO)",
        "https://ico.org.uk",
        Guarda(fonte="Records Management Code of Practice"),
    ),
    "CA": Legislacao(
        "PIPEDA and provincial health privacy laws (such as PHIPA in Ontario)",
        "PIPEDA",
        "Office of the Privacy Commissioner of Canada",
        "https://www.priv.gc.ca",
        Guarda(varia=PROVINCIA),
    ),
    "AU": Legislacao(
        "Privacy Act 1988 (Australian Privacy Principles)",
        "Privacy Act 1988",
        "Office of the Australian Information Commissioner (OAIC)",
        "https://www.oaic.gov.au",
        Guarda(varia=ESTADO),
    ),
    "ZA": Legislacao(
        "Protection of Personal Information Act (POPIA, Act 4 of 2013)",
        "POPIA",
        "Information Regulator",
        "https://inforegulator.org.za",
        Guarda(6, 21, fonte="HPCSA, Booklet 9"),
    ),
}


def do_pais(country=None):
    return LEIS.get(country or countries.pais_da_clinica(), LEIS[countries.PADRAO])


def prazo_de_guarda(country=None):
    """One sentence on how long the country keeps health records, in the user's language."""
    guarda = do_pais(country).guarda
    if guarda.anos and guarda.ate_idade:
        return _(
            "O prontuário deve ser guardado por pelo menos %(anos)s anos depois do último "
            "registro e, de menores de idade, até o paciente fazer %(idade)s anos, se for mais "
            "tarde (%(fonte)s)."
        ) % {"anos": guarda.anos, "idade": guarda.ate_idade, "fonte": guarda.fonte}
    if guarda.anos:
        return _(
            "O prontuário deve ser guardado por pelo menos %(anos)s anos depois do último "
            "registro (%(fonte)s)."
        ) % {"anos": guarda.anos, "fonte": guarda.fonte}
    if guarda.varia == ESTADO:
        return _("O prazo de guarda do prontuário é definido pela lei de cada estado.")
    if guarda.varia == PROVINCIA:
        return _("O prazo de guarda do prontuário é definido pela lei de cada província.")
    if guarda.fonte:
        return _(
            "O prazo de guarda do prontuário segue %(fonte)s: confira o prazo atual com a "
            "autoridade de saúde."
        ) % {"fonte": guarda.fonte}
    return _("Confira com a autoridade de saúde do país o prazo de guarda do prontuário.")
