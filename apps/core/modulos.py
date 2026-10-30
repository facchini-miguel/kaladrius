"""Modules the clinic turns on or off, independent from the user's role (decision 092).

The specialties (Odontologia, Medicina) and the general modules (schedule, medical record,
estimates, finance, recalls, birthdays) combine freely, except for DEPENDENCIAS.
Disabling a module never removes its stored data.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .isolamento import sem_isolamento
from .models import DEPENDENCIAS, MODULOS_GERAIS, Clinica, ModuloClinico, ModuloDaClinica


def iniciais(area):
    """A new clinic: its area's specialty and every general module."""
    return {area} & set(ModuloClinico.values) | MODULOS_GERAIS


def faltando(codigos):
    """{module: missing modules it depends on} for the modules in `codigos`."""
    codigos = set(codigos)
    return {
        modulo: precisa - codigos
        for modulo, precisa in DEPENDENCIAS.items()
        if modulo in codigos and not precisa <= codigos
    }


def habilitados(request):
    """Enabled module codes of the request's clinic, read once per request."""
    if not hasattr(request, "_modulos_habilitados"):
        clinica = getattr(request, "clinica", None)
        request._modulos_habilitados = (
            frozenset(
                ModuloDaClinica.todos.filter(clinica=clinica, ativo=True).values_list(
                    "codigo", flat=True
                )
            )
            if clinica is not None and clinica.pk is not None
            else frozenset()
        )
    return request._modulos_habilitados


@transaction.atomic
def configurar(clinica, codigos):
    """Replace the enabled modules, retaining disabled rows and their audit history.

    `codigos` is the whole set to leave on. Called after the caller's authorization
    (clinic settings/admin). Clinic locking is shared with dental writes, so disabling
    cannot race a new specialized item.
    """
    codigos = set(codigos)
    if not codigos <= set(ModuloClinico.values):
        raise ValidationError(_("Módulo clínico desconhecido."))
    if faltando(codigos):
        raise ValidationError(_("Orçamentos precisa do Financeiro habilitado."))
    if clinica.pk is None:
        raise ValidationError(_("Cadastre a clínica antes de configurar os módulos."))
    Clinica.objects.select_for_update().get(pk=clinica.pk)
    # Administrative configuration has an explicit clinic; the ordinary model manager
    # remains isolated for queries from all the other modules.
    with sem_isolamento():
        for codigo in ModuloClinico:
            modulo, criado = ModuloDaClinica.objects.get_or_create(
                clinica=clinica, codigo=codigo, defaults={"ativo": codigo in codigos}
            )
            if not criado and modulo.ativo != (codigo in codigos):
                modulo.ativo = codigo in codigos
                modulo.save(update_fields=["ativo"])
