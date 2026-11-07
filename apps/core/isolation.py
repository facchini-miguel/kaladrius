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
from django.utils.translation import gettext_lazy as _

_current_clinic = ContextVar("current_clinic", default=None)
_isolation_off = ContextVar("isolation_off", default=False)


class NoCurrentClinic(RuntimeError):
    """Clinic data was accessed while no current clinic was set."""


class WrongClinic(RuntimeError):
    """A row from another clinic was about to be saved or deleted."""


def current_clinic():
    return _current_clinic.get()


def isolation_active():
    return not _isolation_off.get()


@contextlib.contextmanager
def use_clinic(clinic):
    """Run the block with `clinica` as the current clinic."""
    token = _current_clinic.set(clinic)
    try:
        yield clinic
    finally:
        _current_clinic.reset(token)


@contextlib.contextmanager
def without_isolation():
    """Run the block with access to every clinic. Platform-level code only."""
    token = _isolation_off.set(True)
    try:
        yield
    finally:
        _isolation_off.reset(token)


class CurrentClinicFilter(models.Expression):
    """WHERE condition "clinica_id = <current clinic>", resolved when the SQL is compiled.

    Deciding at execution time (not when the queryset is built) lets Django build
    querysets at import time, e.g. the choices of a form field, while every query
    that actually runs is still filtered by the clinic current at that moment.
    """

    output_field = models.BooleanField()
    conditional = True

    def __init__(self, column=None):
        super().__init__()
        self.column = column

    def get_source_expressions(self):
        return [self.column] if self.column is not None else []

    def set_source_expressions(self, expressions):
        self.column = expressions[0] if expressions else None

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        duplicate = self.copy()
        duplicate.column = models.F("clinic_id").resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        return duplicate

    def as_sql(self, compiler, connection):
        if not isolation_active():
            return "(1 = 1)", []
        clinic = current_clinic()
        if clinic is None:
            raise NoCurrentClinic("Clinic data queried with no current clinic set.")
        column, parameters = compiler.compile(self.column)
        return f"({column} = %s)", [*parameters, clinic.pk]


class ClinicManager(models.Manager):
    """Default manager that only sees rows from the current clinic (checked on execution)."""

    def get_queryset(self):
        return super().get_queryset().filter(CurrentClinicFilter())


class ClinicModel(models.Model):
    """Base class for every model that belongs to a clinic."""

    clinic = models.ForeignKey(
        "core.Clinic",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("clínica"),
    )

    # The first manager declared is Django's default manager, so the isolated one must
    # come first. Do not reorder (a test checks this for every clinic model).
    objects = ClinicManager()
    # Unfiltered access, for platform-level code that already uses sem_isolamento().
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._check_clinic()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_clinic()
        return super().delete(*args, **kwargs)

    def _check_clinic(self):
        """Fill in the current clinic on new rows and block writes to other clinics."""
        if not isolation_active():
            return
        current = current_clinic()
        if current is None:
            raise NoCurrentClinic(f"{type(self).__name__}: no current clinic is set.")
        if self.clinic_id is None:
            self.clinic = current
        elif self.clinic_id != current.pk:
            raise WrongClinic(
                f"{type(self).__name__} {self.pk} belongs to clinic {self.clinic_id}, "
                f"not to the current clinic {current.pk}."
            )
