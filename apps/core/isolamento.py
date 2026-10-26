"""Per-clinic data isolation (multi-tenancy).

Every model holding clinic data inherits from ModeloDaClinica. Its default manager
only returns rows from the current clinic, which ClinicaAtualMiddleware sets for each
request. Without a current clinic the manager raises SemClinicaAtual (fail closed), so
a forgotten filter can never leak another clinic's data.

Platform-level code (Django admin, management commands) that legitimately needs every
clinic must opt in explicitly with `sem_isolamento()`.
"""

import contextlib
from contextvars import ContextVar

from django.db import models

_clinica_atual = ContextVar("clinica_atual", default=None)
_isolamento_desligado = ContextVar("isolamento_desligado", default=False)


class SemClinicaAtual(RuntimeError):
    """Clinic data was accessed while no current clinic was set."""


class ClinicaDiferente(RuntimeError):
    """A row from another clinic was about to be saved or deleted."""


def clinica_atual():
    return _clinica_atual.get()


def isolamento_ativo():
    return not _isolamento_desligado.get()


@contextlib.contextmanager
def usar_clinica(clinica):
    """Run the block with `clinica` as the current clinic."""
    token = _clinica_atual.set(clinica)
    try:
        yield clinica
    finally:
        _clinica_atual.reset(token)


@contextlib.contextmanager
def sem_isolamento():
    """Run the block with access to every clinic. Platform-level code only."""
    token = _isolamento_desligado.set(True)
    try:
        yield
    finally:
        _isolamento_desligado.reset(token)


class FiltroClinicaAtual(models.Expression):
    """WHERE condition "clinica_id = <current clinic>", resolved when the SQL is compiled.

    Deciding at execution time (not when the queryset is built) lets Django build
    querysets at import time, e.g. the choices of a form field, while every query
    that actually runs is still filtered by the clinic current at that moment.
    """

    output_field = models.BooleanField()
    conditional = True

    def __init__(self, coluna=None):
        super().__init__()
        self.coluna = coluna

    def get_source_expressions(self):
        return [self.coluna] if self.coluna is not None else []

    def set_source_expressions(self, expressoes):
        self.coluna = expressoes[0] if expressoes else None

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        copia = self.copy()
        copia.coluna = models.F("clinica_id").resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        return copia

    def as_sql(self, compiler, connection):
        if not isolamento_ativo():
            return "(1 = 1)", []
        clinica = clinica_atual()
        if clinica is None:
            raise SemClinicaAtual("Clinic data queried with no current clinic set.")
        coluna, parametros = compiler.compile(self.coluna)
        return f"({coluna} = %s)", [*parametros, clinica.pk]


class ClinicaManager(models.Manager):
    """Default manager that only sees rows from the current clinic (checked on execution)."""

    def get_queryset(self):
        return super().get_queryset().filter(FiltroClinicaAtual())


class ModeloDaClinica(models.Model):
    """Base class for every model that belongs to a clinic."""

    clinica = models.ForeignKey(
        "core.Clinica",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="clínica",
    )

    # The first manager declared is Django's default manager, so the isolated one must
    # come first. Do not reorder (a test checks this for every clinic model).
    objects = ClinicaManager()
    # Unfiltered access, for platform-level code that already uses sem_isolamento().
    todos = models.Manager()  # noqa: DJ012

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._conferir_clinica()
        return super().delete(*args, **kwargs)

    def _conferir_clinica(self):
        """Fill in the current clinic on new rows and block writes to other clinics."""
        if not isolamento_ativo():
            return
        atual = clinica_atual()
        if atual is None:
            raise SemClinicaAtual(f"{type(self).__name__}: no current clinic is set.")
        if self.clinica_id is None:
            self.clinica = atual
        elif self.clinica_id != atual.pk:
            raise ClinicaDiferente(
                f"{type(self).__name__} {self.pk} belongs to clinic {self.clinica_id}, "
                f"not to the current clinic {atual.pk}."
            )
