"""Helpers for made-up data: the test and demo data (seed_sample_data) and the
anonymization of imported data (apps/legacy/anonymization.py). Decision 131."""

from apps.core.validators import cnpj_valido, cpf_valido, somente_digitos


def _valido(gerar, valido):
    while True:
        document = somente_digitos(gerar())
        if valido(document):
            return document


def cpf(fake):
    """A CPF the system accepts: since Faker 40 one with all digits equal (000.000.000-00),
    which the Receita rejects, can come out, rarely."""
    return _valido(fake.cpf, cpf_valido)


def cnpj(fake):
    return _valido(fake.cnpj, cnpj_valido)


def occupation(fake):
    """A Faker job title that fits `Paciente.profissao`, drawn again instead of cut: since
    Faker 40 the pt_BR list has titles longer than the field."""
    from apps.patients.models import Patient

    limit = Patient._meta.get_field("occupation").max_length
    return next(titulo for titulo in iter(fake.job, None) if len(titulo) <= limit)
