"""The stored choice values before and after the English codes (decisions 197 and 198).

The codes a choice field stores (`agendado`, `dinheiro`, `recepcao`…) become English, each its
member's name (`Appointment.Status.BOOKED` → `booked`). `sync_values` converts the rows to the
values the running code uses, in either direction, after `migrate`
(apps/core/management/commands/migrate.py): the version before the change and the one after it
work on the same database, so the automatic rollback works, and a restored backup or the
demo's base is converted by the version that migrates it.

What a person typed is never converted: only these fields' codes.
"""

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import connections, transaction

# "app_label.Model.field": {Portuguese value: English value}. Values that are the same in both
# (admin, login, logout, pix, boleto, cheque, hsa, bpay) are not listed.
VALUES = {
    "core.Clinic.area": {"odontologia": "dentistry", "medicina": "medicine", "outra": "other"},
    "core.ClinicModule.code": {
        "odontologia": "dentistry",
        "medicina": "medicine",
        "agenda": "schedule",
        "prontuario": "medical_records",
        "orcamentos": "estimates",
        "financeiro": "finance",
        "rechamadas": "recalls",
        "aniversariantes": "birthdays",
        "convenios": "health_plans",
        "pessoal": "staff",
    },
    "core.Membership.role": {
        "recepcao": "front_desk",
        "profissional": "practitioner",
        "financeiro": "finance",
    },
    "schedule.Appointment.status": {
        "agendado": "booked",
        "compareceu": "attended",
        "faltou": "missed",
        "desmarcou": "cancelled",
    },
    "patients.Patient.kind": {"PF": "individual", "PJ": "company"},
    "patients.RelatedPerson.relationship": {
        "mae": "mother",
        "pai": "father",
        "responsavel": "guardian",
        "conjuge": "spouse",
        "filho": "child",
        "irmao": "sibling",
        "avo": "grandparent",
        "neto": "grandchild",
        "parente": "relative",
        "emergencia": "emergency",
        "contato": "contact",
    },
    "audit.AuditEntry.action": {
        "criar": "create",
        "alterar": "change",
        "excluir": "delete",
        "visualizar": "viewed",
        "login_falhou": "login_failed",
    },
    "finance.FinancialAccount.kind": {"dinheiro": "cash", "banco": "bank", "cartao": "card"},
    "finance.AccountGroup.kind": {"receita": "income", "despesa": "expense"},
    "finance.Category.kind": {"receita": "income", "despesa": "expense"},
    "finance.Supplier.kind": {"PF": "individual", "PJ": "company"},
    "finance.Entry.kind": {"receber": "receivable", "pagar": "payable"},
    "finance.Payment.method": {
        "dinheiro": "cash",
        "debito": "debit",
        "credito": "credit",
        "transferencia": "transfer",
        "carteira": "wallet",
        "debito_auto": "direct_debit",
        "financiamento": "financing",
    },
    "finance.CashMovement.kind": {"retirada": "withdrawal", "reforco": "top_up"},
    "finance.BankTransaction.status": {
        "pendente": "pending",
        "conciliada": "reconciled",
        "ignorada": "ignored",
    },
    "estimates.Estimate.status": {"aberto": "open", "aprovado": "approved", "recusado": "refused"},
    "medical_records.Certificate.kind": {
        "comparecimento": "attendance",
        "afastamento": "sick_leave",
    },
}


def both_spellings(key, values):
    """The field's values in both spellings, sorted: for a check constraint that must hold
    before and after a conversion."""
    mapping = VALUES[key]
    return sorted({*values, *mapping, *mapping.values()})


def spellings(key, value):
    """One value in both spellings, sorted: for a constraint's condition."""
    mapping = VALUES[key]
    other = mapping.get(value) or {e: p for p, e in mapping.items()}.get(value)
    return sorted({value, other})


def direction(mapping, current):
    """{value to convert: value of the running code} for a field whose code has the values
    `current`: back to Portuguese while the code is Portuguese, to English after."""
    if set(mapping) & set(current):
        return {english: portuguese for portuguese, english in mapping.items()}
    return dict(mapping)


def field_pairs():
    """(model, field, {value to convert: code's value}) for each field the code still has."""
    for key, mapping in VALUES.items():
        app_label, model_name, field_name = key.split(".")
        try:
            model = apps.get_model(app_label, model_name)
            field = model._meta.get_field(field_name)
        except (LookupError, FieldDoesNotExist):
            continue
        yield model, field, direction(mapping, [value for value, _label in field.choices])


def code_value(key, value):
    """The running code's value for a stored one in either spelling (the audit log keeps the
    values of its time)."""
    app_label, model_name, field_name = key.split(".")
    field = apps.get_model(app_label, model_name)._meta.get_field(field_name)
    return direction(VALUES[key], [v for v, _label in field.choices]).get(value, value)


def sync_values(using="default"):
    """Convert the other spelling's rows to the running code's values. Returns what changed:
    [("app_label.Model.field", rows converted)]."""
    connection = connections[using]
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
    changed = []
    with transaction.atomic(using=using), connection.cursor() as cursor:
        for model, field, pairs in field_pairs():
            table = model._meta.db_table
            if table not in tables or not pairs:
                continue
            columns = {
                c.name for c in connection.introspection.get_table_description(cursor, table)
            }
            if field.column not in columns:
                continue
            rows = _convert(cursor, connection, model, field, pairs)
            if rows:
                changed.append((f"{model._meta.label}.{field.name}", rows))
    return changed


def _convert(cursor, connection, model, field, pairs):
    quote = connection.ops.quote_name
    table, column = quote(model._meta.db_table), quote(field.column)
    cases = " ".join("WHEN %s THEN %s" for _ in pairs)
    params = [value for pair in pairs.items() for value in pair]
    placeholders = ", ".join(["%s"] * len(pairs))
    cursor.execute(
        f"UPDATE {table} SET {column} = CASE {column} {cases} END "  # noqa: S608
        f"WHERE {column} IN ({placeholders})",
        [*params, *pairs],
    )
    return cursor.rowcount
