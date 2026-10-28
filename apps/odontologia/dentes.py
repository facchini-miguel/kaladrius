"""The dental module (decision 080): what only clinics in the Odontologia area use.

Shown only when the clinic's area is Odontologia (Clinica.odontologia): the dental chart and
the teeth and faces of estimate items. The tooth fields stay in the estimates' database, so
changing the area hides or shows them without losing anything.
"""

# FDI two-digit tooth numbers, in the order of the dental chart (patient's right first).
DENTES_PERMANENTES = [
    [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28],
    [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38],
]
DENTES_DECIDUOS = [
    [55, 54, 53, 52, 51, 61, 62, 63, 64, 65],
    [85, 84, 83, 82, 81, 71, 72, 73, 74, 75],
]
DENTES_VALIDOS = {d for linha in DENTES_PERMANENTES + DENTES_DECIDUOS for d in linha}

# Appointment types a new dental clinic starts with: the ones from the legacy system, with
# the same colors.
TIPOS_DE_ATENDIMENTO = [
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


def odontograma(selecionados):
    """Template context of the dental chart (templates/odontologia/_odontograma.html)."""
    return {
        "permanentes": DENTES_PERMANENTES,
        "deciduos": DENTES_DECIDUOS,
        "selecionados": selecionados,
    }
