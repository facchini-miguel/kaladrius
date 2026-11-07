"""The stored choice values in English (decision 198): each value becomes its member's name.

The map is frozen here, as it was when written. `migrate` also converts the values to the
running code's after every whole migrate (apps/core/values.py), so the version before this one,
after an automatic rollback, puts them back in Portuguese.
"""

from django.db import migrations

# (table, column, {Portuguese: English})
VALUES = [
    ("core_clinic", "area", {'odontologia': 'dentistry', 'medicina': 'medicine', 'outra': 'other'}),
    ("core_clinic_module", "code", {'odontologia': 'dentistry', 'medicina': 'medicine', 'agenda': 'schedule', 'prontuario': 'medical_records', 'orcamentos': 'estimates', 'financeiro': 'finance', 'rechamadas': 'recalls', 'aniversariantes': 'birthdays', 'convenios': 'health_plans', 'pessoal': 'staff'}),
    ("core_membership", "role", {'recepcao': 'front_desk', 'profissional': 'practitioner', 'financeiro': 'finance'}),
    ("schedule_appointment", "status", {'agendado': 'booked', 'compareceu': 'attended', 'faltou': 'missed', 'desmarcou': 'cancelled'}),
    ("patients_patient", "kind", {'PF': 'individual', 'PJ': 'company'}),
    ("patients_related_person", "relationship", {'mae': 'mother', 'pai': 'father', 'responsavel': 'guardian', 'conjuge': 'spouse', 'filho': 'child', 'irmao': 'sibling', 'avo': 'grandparent', 'neto': 'grandchild', 'parente': 'relative', 'emergencia': 'emergency', 'contato': 'contact'}),
    ("audit_entry", "action", {'criar': 'create', 'alterar': 'change', 'excluir': 'delete', 'visualizar': 'viewed', 'login_falhou': 'login_failed'}),
    ("finance_financial_account", "kind", {'dinheiro': 'cash', 'banco': 'bank', 'cartao': 'card'}),
    ("finance_account_group", "kind", {'receita': 'income', 'despesa': 'expense'}),
    ("finance_category", "kind", {'receita': 'income', 'despesa': 'expense'}),
    ("finance_supplier", "kind", {'PF': 'individual', 'PJ': 'company'}),
    ("finance_entry", "kind", {'receber': 'receivable', 'pagar': 'payable'}),
    ("finance_payment", "method", {'dinheiro': 'cash', 'debito': 'debit', 'credito': 'credit', 'transferencia': 'transfer', 'carteira': 'wallet', 'debito_auto': 'direct_debit', 'financiamento': 'financing'}),
    ("finance_cash_movement", "kind", {'retirada': 'withdrawal', 'reforco': 'top_up'}),
    ("finance_bank_transaction", "status", {'pendente': 'pending', 'conciliada': 'reconciled', 'ignorada': 'ignored'}),
    ("estimates_estimate", "status", {'aberto': 'open', 'aprovado': 'approved', 'recusado': 'refused'}),
    ("medical_records_certificate", "kind", {'comparecimento': 'attendance', 'afastamento': 'sick_leave'}),
]


def _convert(schema_editor, forward):
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table, column, mapping in VALUES:
            pairs = mapping if forward else {e: p for p, e in mapping.items()}
            cases = " ".join("WHEN %s THEN %s" for _ in pairs)
            placeholders = ", ".join(["%s"] * len(pairs))
            cursor.execute(
                f"UPDATE {quote(table)} SET {quote(column)} = CASE {quote(column)} {cases} END "  # noqa: S608
                f"WHERE {quote(column)} IN ({placeholders})",
                [*(v for pair in pairs.items() for v in pair), *pairs],
            )


def to_english(apps, schema_editor):
    _convert(schema_editor, forward=True)


def to_portuguese(apps, schema_editor):
    _convert(schema_editor, forward=False)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0008_english_stored_values"),
        ("core", "0030_english_stored_values"),
        ("estimates", "0014_english_stored_values"),
        ("finance", "0028_english_stored_values"),
        ("medical_records", "0015_english_stored_values"),
        ("patients", "0018_english_stored_values"),
        ("schedule", "0016_english_stored_values"),
    ]

    operations = [migrations.RunPython(to_english, to_portuguese)]
