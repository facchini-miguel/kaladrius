"""Clinical capabilities, independent from the user's role and primary clinic area.

The shared medical record, schedule and finance do not require either specialty.
Disabling a specialty never removes its stored data.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .isolamento import sem_isolamento
from .models import Clinica, ModuloClinico, ModuloDaClinica


def iniciais(area):
    return {area} if area in ModuloClinico.values else set()


@transaction.atomic
def configurar(clinica, codigos):
    """Replace enabled specialties, retaining disabled rows and their audit history.

    Called after the caller's authorization (clinic settings/admin). Clinic locking is
    shared with dental writes, so disabling cannot race a new specialized item.
    """
    codigos = set(codigos)
    if not codigos <= set(ModuloClinico.values):
        raise ValidationError(_("Módulo clínico desconhecido."))
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
