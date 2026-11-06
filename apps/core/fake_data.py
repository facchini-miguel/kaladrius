"""Helpers for made-up data: the test and demo data (seed_sample_data) and the
anonymization of imported data (apps/legacy/anonymization.py). Decision 131."""

from apps.core.validators import digits_only, valid_cnpj, valid_cpf


def _valid(generate, is_valid):
    while True:
        document = digits_only(generate())
        if is_valid(document):
            return document


def cpf(fake):
    """A CPF the system accepts: since Faker 40 one with all digits equal (000.000.000-00),
    which the Receita rejects, can come out, rarely."""
    return _valid(fake.cpf, valid_cpf)


def cnpj(fake):
    return _valid(fake.cnpj, valid_cnpj)


def occupation(fake):
    """A Faker job title that fits `Paciente.profissao`, drawn again instead of cut: since
    Faker 40 the pt_BR list has titles longer than the field."""
    from apps.patients.models import Patient

    limit = Patient._meta.get_field("occupation").max_length
    return next(title for title in iter(fake.job, None) if len(title) <= limit)
