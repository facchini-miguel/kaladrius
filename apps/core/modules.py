"""Modules the clinic turns on or off, independent from the user's role (decision 092).

The specialties (Odontologia, Medicina) and the general modules (schedule, medical record,
estimates, finance, recalls, birthdays) combine freely, except for DEPENDENCIAS.
Disabling a module never removes its stored data.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .isolation import sem_isolamento
from .models import DEPENDENCIAS, MODULOS_GERAIS, Clinic, ClinicModule, ModuloClinico


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
        clinic = getattr(request, "clinic", None)
        request._modulos_habilitados = (
            frozenset(
                ClinicModule.todos.filter(clinic=clinic, ativo=True).values_list(
                    "codigo", flat=True
                )
            )
            if clinic is not None and clinic.pk is not None
            else frozenset()
        )
    return request._modulos_habilitados


def visiveis(request):
    """Modules the user reaches: the enabled ones, and every one for the system administrator
    (decision 115), who sees a turned-off module, marked as off, to maintain it or to try it
    before turning it on. The team never sees a turned-off module."""
    user = getattr(request, "user", None)
    if user is not None and user.is_superuser and getattr(request, "clinic", None):
        return frozenset(ModuloClinico.values)
    return habilitados(request)


def desligados_visiveis(request):
    """Turned-off modules the user still sees: only the system administrator has any."""
    return visiveis(request) - habilitados(request)


def marcar_se_desligado(request, codigo):
    """A page of a turned-off module that the system administrator opened: base.html warns."""
    if codigo and codigo not in habilitados(request):
        request.modulo_desligado = ModuloClinico(codigo)


@transaction.atomic
def configurar(clinic, codigos):
    """Replace the enabled modules, retaining disabled rows and their audit history.

    `codigos` is the whole set to leave on. Called after the caller's authorization
    (clinic settings/admin). Clinic locking is shared with dental writes, so disabling
    cannot race a new specialized item.
    """
    codigos = set(codigos)
    if not codigos <= set(ModuloClinico.values):
        raise ValidationError(_("Módulo clínico desconhecido."))
    if faltando(codigos):
        raise ValidationError(_("Orçamentos e Pessoal precisam do Financeiro habilitado."))
    if clinic.pk is None:
        raise ValidationError(_("Cadastre a clínica antes de configurar os módulos."))
    Clinic.objects.select_for_update().get(pk=clinic.pk)
    # Administrative configuration has an explicit clinic; the ordinary model manager
    # remains isolated for queries from all the other modules.
    with sem_isolamento():
        for codigo in ModuloClinico:
            modulo, criado = ClinicModule.objects.get_or_create(
                clinic=clinic, codigo=codigo, defaults={"ativo": codigo in codigos}
            )
            if not criado and modulo.ativo != (codigo in codigos):
                modulo.ativo = codigo in codigos
                modulo.save(update_fields=["ativo"])
