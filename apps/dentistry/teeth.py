"""The dental module (decision 080): what only clinics in the Odontologia area use.

Shown only when the clinic's area is Odontologia (Clinica.odontologia): the dental chart and
the teeth and faces of estimate items. The tooth fields stay in the estimates' database, so
changing the area hides or shows them without losing anything.
"""

from django.utils.translation import gettext_lazy as _

# FDI two-digit tooth numbers, in the order of the dental chart (patient's right first).
PERMANENT_TEETH = [
    [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28],
    [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38],
]
PRIMARY_TEETH = [
    [55, 54, 53, 52, 51, 61, 62, 63, 64, 65],
    [85, 84, 83, 82, 81, 71, 72, 73, 74, 75],
]
VALID_TEETH = {d for row in PERMANENT_TEETH + PRIMARY_TEETH for d in row}

# How teeth are named on screen and paper (decision 122). They are always stored in FDI; the
# clinic chooses the numbering, by default its country's (Universal in the United States).
FDI, UNIVERSAL, PALMER = "fdi", "universal", "palmer"
NUMBERINGS = [
    (FDI, _("FDI (11 a 48; dentes de leite 51 a 85)")),
    (UNIVERSAL, _("Universal, dos Estados Unidos (1 a 32; dentes de leite A a T)")),
    (PALMER, _("Palmer (UR6, LL3; dentes de leite URE a LRE)")),
]
LEGENDS = {
    FDI: _("Numeração FDI."),
    UNIVERSAL: _("Numeração universal (Estados Unidos)."),
    PALMER: _(
        "Notação de Palmer: UR superior direito, UL superior esquerdo, LL inferior esquerdo, "
        "LR inferior direito."
    ),
}
UNIVERSAL_LETTERS = "ABCDEFGHIJKLMNOPQRST"
_PALMER_QUADRANTS = {1: "UR", 2: "UL", 3: "LL", 4: "LR"}


def clinic_numbering():
    from apps.core.isolation import current_clinic

    return getattr(current_clinic(), "tooth_numbering", None) or FDI


def _universal(dente):
    """1 to 32 from the upper right third molar around to the lower right one; baby teeth A to
    T in the same order."""
    quadrante, number = divmod(dente, 10)
    if quadrante <= 4:
        return {1: 9 - number, 2: 8 + number, 3: 25 - number, 4: 24 + number}[quadrante]
    return UNIVERSAL_LETTERS[
        {5: 5 - number, 6: 4 + number, 7: 15 - number, 8: 14 + number}[quadrante]
    ]


def name(dente, numeracao=None):
    """The FDI tooth as the clinic writes it: 18 → "18", "1" (Universal) or "UR8" (Palmer)."""
    dente = int(dente)
    numeracao = numeracao or clinic_numbering()
    if dente not in VALID_TEETH or numeracao == FDI:
        return str(dente)
    if numeracao == UNIVERSAL:
        return str(_universal(dente))
    quadrante, number = divmod(dente, 10)
    lado = _PALMER_QUADRANTS[(quadrante - 1) % 4 + 1]
    return lado + (str(number) if quadrante <= 4 else "ABCDE"[number - 1])


def sort_teeth(teeth, numeracao=None):
    """Teeth in the numbering's order: 1, 3, 14, A in Universal; FDI order otherwise."""
    numeracao = numeracao or clinic_numbering()
    if numeracao != UNIVERSAL:
        return sorted(teeth)

    def key(dente):
        value = _universal(dente) if dente in VALID_TEETH else 99
        return (isinstance(value, str), str(value).zfill(2))

    return sorted(teeth, key=key)


# Appointment types a new dental clinic starts with: the ones from the legacy system, with
# the same colors.
APPOINTMENT_TYPES = [
    ("Liberado", "#b9f1a7"),
    ("Cirurgia", "#f7a5a5"),
    ("Dentística", "#f6f7a5"),
    ("Periodontia", "#7b88cb"),
    ("Consulta inicial", "#e7a5f7"),
    ("Prótese", "#fed27d"),
    ("Endodontia", "#e96cd9"),
    ("Ortodontia", "#a7eef1"),
    ("Atendimento de 15 em 15", "#d5dae6"),
    ("Ocupado", "#a7bef1"),
]


def odontogram(selecionados):
    """Template context of the dental chart (templates/dentistry/_odontogram.html)."""
    return {
        "permanent_rows": PERMANENT_TEETH,
        "primary_rows": PRIMARY_TEETH,
        "selected": selecionados,
    }
