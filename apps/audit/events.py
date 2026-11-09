"""What the system itself writes in the audit log (decision 206): an event code and its values,
shown in the reader's language.

The entry also keeps the text in the source language (settings.LANGUAGE_CODE) in
`object_repr`, as it always did, so the search and the Django admin still find it. Entries
written before decision 206 have no event; they show in the reader's language too when their
Portuguese text is one the system wrote (OLD_TEXTS).
"""

import re

from django.utils.translation import gettext_lazy as _

TWO_FACTOR_ON = "two_factor_on"
TWO_FACTOR_OFF = "two_factor_off"
TWO_FACTOR_REMOVED = "two_factor_removed"
LOGIN_FAILED = "login_failed"
PERSONAL_DATA_ERASED = "personal_data_erased"
PERSONAL_DATA_REMOVED = "personal_data_removed"
PRINTED = "printed"
ATTACHMENT = "attachment"
SAMPLE_DATA_REMOVED = "sample_data_removed"
LEGACY_IMPORT = "legacy_import"
LEGACY_ANONYMIZED = "legacy_anonymized"

TEXTS = {
    TWO_FACTOR_ON: _("%(record)s: two-step verification turned on"),
    TWO_FACTOR_OFF: _("%(record)s: two-step verification turned off"),
    TWO_FACTOR_REMOVED: _("%(record)s: two-step verification removed by the administrator"),
    LOGIN_FAILED: _("username entered: %(record)s"),
    PERSONAL_DATA_ERASED: _(
        "Patient %(record)s: personal data deleted at the data subject's request"
    ),
    # %(model)s is the kind of record, filled when the entry is shown.
    PERSONAL_DATA_REMOVED: _("%(model)s %(record)s (data removed)"),
    PRINTED: _("%(record)s (printout)"),
    ATTACHMENT: _("%(record)s – attachment"),
    SAMPLE_DATA_REMOVED: _(
        "Sample data removed: %(clinics)s clinics, %(patients)s patients, %(users)s users"
    ),
    LEGACY_IMPORT: _(
        "Import from the old system: %(patients)s patients, %(appointments)s appointments, "
        "%(recalls)s recalls"
    ),
    LEGACY_ANONYMIZED: _(
        "Data anonymized: %(patients)s patients, %(appointments)s appointments, "
        "%(recalls)s recalls, %(practitioners)s practitioners"
    ),
}

# Values written in `changes` instead of the real ones, and the Portuguese words entries
# stored before decision 206.
REMOVED = "(removed)"
CLINICAL_CONTENT = "(clinical content)"
VALUES = {
    REMOVED: _("(removed)"),
    "(removido)": _("(removed)"),
    CLINICAL_CONTENT: _("(clinical content)"),
    "(conteúdo clínico)": _("(clinical content)"),
}

# The texts the system wrote in Portuguese before decision 206, as patterns of their values.
_COUNT = r"(?P<{}>\d+) {}"
OLD_TEXTS = [
    (re.compile(r"(?P<record>.+): verificação em duas etapas ativada"), TWO_FACTOR_ON),
    (re.compile(r"(?P<record>.+): verificação em duas etapas desativada"), TWO_FACTOR_OFF),
    (
        re.compile(r"(?P<record>.+): verificação em duas etapas removida pelo administrador"),
        TWO_FACTOR_REMOVED,
    ),
    (re.compile(r"usuário informado: (?P<record>.*)"), LOGIN_FAILED),
    (
        re.compile(r"Paciente (?P<record>\S+): dados pessoais excluídos a pedido do titular"),
        PERSONAL_DATA_ERASED,
    ),
    (re.compile(r".+ (?P<record>\S+) \(dados removidos\)"), PERSONAL_DATA_REMOVED),
    (re.compile(r"(?P<record>.+) \(impressão\)"), PRINTED),
    # Written in the language of whoever added, opened or removed the file.
    (re.compile(r"(?P<record>.+) – (anexo|adjunto|attachment)"), ATTACHMENT),
    (
        re.compile(
            "Dados de teste removidos: "
            + ", ".join(
                _COUNT.format(name, word)
                for name, word in [
                    ("clinics", "clínicas"),
                    ("patients", "pacientes"),
                    ("users", "usuários"),
                ]
            )
        ),
        SAMPLE_DATA_REMOVED,
    ),
    (
        re.compile(
            "Importação do sistema antigo: "
            + ", ".join(
                _COUNT.format(name, word)
                for name, word in [
                    ("patients", "pacientes"),
                    ("appointments", "agendamentos"),
                    ("recalls", "rechamadas"),
                ]
            )
        ),
        LEGACY_IMPORT,
    ),
    (
        re.compile(
            "Dados anonimizados: "
            + ", ".join(
                _COUNT.format(name, word)
                for name, word in [
                    ("patients", "pacientes"),
                    ("appointments", "agendamentos"),
                    ("recalls", "rechamadas"),
                    ("practitioners", "profissionais"),
                ]
            )
        ),
        LEGACY_ANONYMIZED,
    ),
]


def describe(entry, model=""):
    """The entry's description in the reader's language. `model` is its kind of record, as
    shown to the reader."""
    event, values = entry.event, entry.event_values
    if event not in TEXTS:
        for pattern, old_event in OLD_TEXTS:
            if match := pattern.fullmatch(entry.object_repr):
                event, values = old_event, match.groupdict()
                break
        else:
            return entry.object_repr
    if event == PERSONAL_DATA_REMOVED:
        values = {"record": entry.object_id, **values}
    return TEXTS[event] % {**values, "model": model}


def shown_value(value):
    """A value of `changes` in the reader's language when it stands for a hidden one."""
    return VALUES.get(value, value) if isinstance(value, str) else value
